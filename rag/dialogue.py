"""多轮对话运行时。

模型只会单轮问答，多轮靠这层状态机：
  * 记住上一轮聊的是哪艘船 / 哪件装备
  * 把「那它的中槽呢」「这个多少钱」改写成完整问题
  * 维护对话历史，供界面展示和调试

为什么不让模型自己处理多轮：35M 参数记不住上文实体（评测里 class 类问题
裸模型 0%），而「上一句说的是谁」这件事，代码记一个变量就够了。
"""
from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 指代开头：这些词开头的问句几乎都是追问
FOLLOWUP = re.compile(r"^(那|那么|它|他|她|这个|那个|这套|这套|这艘|该|还有)")
# 追问里只给字段、不给实体：「中槽呢」「护盾容量呢」
ONLY_FIELD = re.compile(r"^([\u4e00-\u9fffA-Za-z ]{2,10}?)(呢|是多少|多少|装什么|\?|？)?$")


@dataclass
class Turn:
    role: str
    content: str
    ts: float = field(default_factory=time.time)


@dataclass
class Session:
    sid: str
    turns: list[Turn] = field(default_factory=list)
    entity: str | None = None       # 当前聊的实体（船/装备名）
    last_field: str | None = None   # 上一轮问的字段
    last_kind: str | None = None    # fact / fit / topic

    def add(self, role: str, content: str) -> None:
        self.turns.append(Turn(role, content))


class Dialogue:
    def __init__(self) -> None:
        from rag.local_model import (FactContext, FitContext, LocalModel,
                                     TopicIndex, answer_with_guard, asked_field)
        from rag.retriever import Retriever

        self.retriever = Retriever()
        self.facts, self.fits = FactContext(), FitContext()
        self.topics = TopicIndex()
        self.model = LocalModel()
        self._asked_field = asked_field
        self._answer = answer_with_guard
        self.sessions: dict[str, Session] = {}

    # ---------------------------------------------------------------- 状态
    def session(self, sid: str | None) -> Session:
        if not sid:
            sid = uuid.uuid4().hex[:12]
        if sid not in self.sessions:
            self.sessions[sid] = Session(sid)
        return self.sessions[sid]

    def _find_entity(self, text: str) -> str | None:
        o = self.facts.find(text)
        return o.get("name_zh") if o else None

    # ---------------------------------------------------------------- 指代改写
    def rewrite(self, question: str, s: Session) -> str:
        """把追问补成完整问题。"""
        q = question.strip()
        ent = self._find_entity(q)
        if ent:
            s.entity = ent
            return q

        if not s.entity:
            return q

        # 「那它的中槽呢」「中槽呢」→「<实体>的中槽装什么」
        # 判定要收紧：之前凡是短句都当追问，结果「无畏舰有几艘？」
        # 被改写成「巴盖斯级无畏舰有几艘？」。
        field = self._asked_field(q)
        is_followup_prefix = bool(FOLLOWUP.match(q))
        is_bare_field = bool(field) and len(q) <= 12
        if not (is_followup_prefix or is_bare_field):
            return q
        if not field and not is_followup_prefix:
            return q
        if field and field in ("高槽", "中槽", "低槽", "改装件", "无人机", "子系统"):
            return f"{s.entity}的{field}装什么？"
        if field:
            return f"{s.entity}的{field}是多少？"
        return f"{s.entity}{q}"

    # ---------------------------------------------------------------- 主入口
    def ask(self, question: str, sid: str | None = None) -> dict:
        s = self.session(sid)
        q2 = self.rewrite(question, s)
        hits = self.retriever.search(q2, k=3)
        res = self._answer(q2, hits, self.model, use_guard=True,
                           facts=self.facts, fits=self.fits, topics=self.topics)

        field = self._asked_field(q2)
        if field:
            s.last_field = field
        s.add("user", question)
        s.add("assistant", res["answer"])

        return {"session_id": s.sid, "question": question,
                "rewritten": q2 if q2 != question else None,
                "answer": res["answer"], "blocked": res["blocked"],
                "entity": s.entity,
                "sources": [h.get("source") for h in hits]}


def cli() -> None:
    d = Dialogue()
    print("EVE 助手（多轮）。输入 exit 退出。\n")
    sid = None
    while True:
        try:
            q = input("你：").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q or q.lower() in ("exit", "quit"):
            break
        r = d.ask(q, sid)
        sid = r["session_id"]
        if r["rewritten"]:
            print(f"  （已改写为：{r['rewritten']}）")
        if r["blocked"]:
            print(f"  ⚠️  {r['blocked']}")
        print(f"助手：{r['answer']}\n")


if __name__ == "__main__":
    cli()

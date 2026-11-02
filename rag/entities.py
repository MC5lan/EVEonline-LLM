"""查询里的 EVE 专有名词识别（最长匹配，锚到 typeID）。

设计原则：这里**不用模型**，用规则。
向量能把「多米尼克斯级」和「多米尼克斯级海军型」算成几乎同一个东西，
而它们的高槽、装甲、抗性完全不同。实体锁定必须是精确的、可复现的、
能解释的——所以它是一个最长匹配扫描器，不是 embedding。

匹配策略：
  * 从每个位置尝试最长可能的名字，命中就整体跳过（避免"伊什塔"又匹配到
    "伊什塔级"的子串）
  * ASCII 不区分大小写；中文原样
  * 太短的（CJK < 2、ASCII < 3）和过于通用的词不进词表
"""
from __future__ import annotations

import json
from pathlib import Path


class EntityIndex:
    def __init__(self, path: str | Path | None = None):
        self.items: dict[str, dict] = {}
        self.max_len = 0
        if path is None:
            path = Path(__file__).resolve().parent.parent / "data" / "entities.jsonl"
        path = Path(path)
        if not path.exists():
            return
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                o = json.loads(line)
                k = (o.get("name") or "").strip().lower()
                if not k:
                    continue
                if k not in self.items:
                    self.items[k] = o
                    self.max_len = max(self.max_len, len(k))

        # 词干表：玩家常说「多米尼克斯」「洛基」，官方名是「多米尼克斯级」。
        # 只去掉结尾的「级」，并且同一词干只保留最短的那个名字
        # （否则「多米尼克斯」会指向「多米尼克斯级海军型」）。
        self.stems: dict[str, str] = {}
        for k in self.items:
            if not k.endswith("级") or len(k) < 4:
                continue
            stem = k[:-1]
            cur = self.stems.get(stem)
            if cur is None or len(k) < len(cur):
                self.stems[stem] = k
        self.stem_len = max((len(s) for s in self.stems), default=0)

    def __len__(self) -> int:
        return len(self.items)

    def find(self, text: str) -> list[dict]:
        """返回按出现顺序去重后的实体列表。"""
        if not self.items or not text:
            return []
        t = text.lower()
        out: list[dict] = []
        seen: set[int] = set()
        i, n = 0, len(t)
        while i < n:
            hit = None
            upper = min(self.max_len, n - i)
            for L in range(upper, 1, -1):
                cand = t[i : i + L]
                if cand in self.items:
                    hit = (cand, L)
                    break
            # 全名没命中，再试词干（「多米尼克斯」->「多米尼克斯级」）
            if hit is None and self.stems:
                upper = min(self.stem_len, n - i)
                for L in range(upper, 2, -1):
                    cand = t[i : i + L]
                    full = self.stems.get(cand)
                    if full:
                        hit = (full, L)
                        break
            if hit:
                rec = self.items[hit[0]]
                tid = int(rec.get("typeID") or 0)
                if tid not in seen:
                    seen.add(tid)
                    out.append({**rec, "matched": hit[0]})
                i += hit[1]
            else:
                i += 1
        return out

    def expand(self, text: str, entities: list[dict]) -> str:
        """把识别到的实体的中英文名补进查询，让 BM25 也能命中另一种写法。"""
        if not entities:
            return text
        extra = []
        for e in entities:
            for k in ("zh", "en"):
                v = (e.get(k) or "").strip()
                if v and v.lower() not in text.lower():
                    extra.append(v)
        return text + (" " + " ".join(dict.fromkeys(extra)) if extra else "")

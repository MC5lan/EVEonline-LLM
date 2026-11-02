"""临时补丁：把丢失的 TopicIndex 重新插入 local_model.py。"""
from pathlib import Path

P = Path(r"D:\Game\eve-lm\rag\local_model.py")

TOPIC = '''class TopicIndex:
    """舰种索引 + 世界观词条的确定性查表。

    这类问题的答案本来就在我们自己建的索引文档里，让 35M 模型去读散文
    是绕远路——直接查表 100% 正确且可追溯。
    """

    def __init__(self):
        import re as _re
        self.groups = {}
        self.entities = {}
        p1 = ROOT / "canonical" / "02_舰船与装配" / "_topic_舰种索引" / "rewrite.md"
        if p1.exists():
            for m in _re.finditer(r"### (.+?)（(\\d+) 艘）\\n(.+)",
                                  p1.read_text(encoding="utf-8")):
                g, n, body = m.group(1), int(m.group(2)), m.group(3)
                names = [x.split("（")[0] for x in body.split("；") if x.strip()]
                self.groups[g] = (n, names)
        p2 = ROOT / "canonical" / "08_剧情与世界观" / "_topic_世界观词条索引" / "rewrite.md"
        if p2.exists():
            for m in _re.finditer(
                    r"### (.+?)\\n- 全库出现 \\*\\*(\\d+)\\*\\* 次(?:.*?)- 原文：「(.+?)」",
                    p2.read_text(encoding="utf-8"), _re.S):
                self.entities[m.group(1)] = (int(m.group(2)), m.group(3))

    def _entry(self, name, max_paras=2):
        p = (ROOT / "canonical" / "08_剧情与世界观" / "词条" / name / "rewrite.md")
        if not p.exists():
            return None
        paras = [x.strip() for x in p.read_text(encoding="utf-8").split("\\n\\n")
                 if len(x.strip()) >= 80
                 and not x.strip().startswith(("#", "分类", "以下"))]
        return "\\n".join(paras[:max_paras]) if paras else None

    def answer(self, question):
        # 最长匹配优先：「枪骑兵级无畏舰」里同时含「无畏舰」
        for g, (n, names) in sorted(self.groups.items(), key=lambda kv: -len(kv[0])):
            if g not in question:
                continue
            if "几艘" in question:
                return f"{g}共 {n} 艘。"
            if "哪些" in question or "有什么船" in question:
                return f"{g}共 {n} 艘：" + "、".join(names[:10]) + "。"
        for e, (cnt, quote) in sorted(self.entities.items(), key=lambda kv: -len(kv[0])):
            if e in question and ("是什么" in question or "是什么地方" in question):
                return self._entry(e) or quote
        return None


'''


def main() -> None:
    s = P.read_text(encoding="utf-8")
    if "class TopicIndex" in s:
        print("已存在，跳过")
        return
    i = s.index("class NumberGuard:")
    s = s[:i] + TOPIC + s[i:]
    P.write_text(s, encoding="utf-8")
    print("TopicIndex 已补回")


if __name__ == "__main__":
    main()

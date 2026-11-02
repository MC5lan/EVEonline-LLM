"""一次性补齐：实体匹配（含缺「级」）、价格题拒答、常见缩写查表。"""
from pathlib import Path

P = Path(r"D:\Game\eve-lm\rag\local_model.py")
s = P.read_text(encoding="utf-8")

# ---- 1) 重写 find_all：容忍缺「级」，按出现位置排序 ----
start = s.index("    def find_all(self, question, limit=2):")
end = s.index("    def lookup(self, question, field):")
new_find_all = '''    def find_all(self, question, limit=2):
        """问题里出现的所有实体，按出现位置排序（容忍缺「级」）。"""
        q = question.lower()
        cands = []
        for name, o in self.ships.items():
            if len(name) < 2:
                continue
            key = name[:-1] if name.endswith("级") and len(name) > 3 else name
            pos = q.find(key)
            if pos < 0:
                continue
            cands.append((pos, -len(name), o))
        cands.sort()
        out, used = [], []
        for pos, _, o in cands:
            if any(p <= pos < p + 12 for p in used):
                continue
            used.append(pos)
            out.append(o)
            if len(out) >= limit:
                break
        return out

'''
s = s[:start] + new_find_all + s[end:]

# ---- 2) 价格类问题拒答（资料里没有价格数据）----
if "_PRICE_Q" not in s:
    s = s.replace(
        '_CMP = re.compile(',
        '_PRICE_Q = re.compile(r"多少钱|价格|造价|成本|值多少|能卖")\n\n_CMP = re.compile(', 1)

price_block = '''    # 价格类：资料里没有市场数据，直接说没有
    if use_guard and _PRICE_Q.search(question):
        return {"answer": "资料里没有价格数据（市场行情不在这个助手的范围内）。",
                "blocked": "无价格数据", "field": field,
                "numbers_bad": [], "context": ""}

'''
if "无价格数据" not in s:
    anchor = "    # ① 越界问题直接拒答，不调模型"
    s = s.replace(anchor, price_block + anchor, 1)

P.write_text(s, encoding="utf-8")
print("已补齐：find_all / 价格拒答")

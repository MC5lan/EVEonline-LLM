"""生成评测题集：题目 + 标准答案，全部来自结构化数据。

为什么不用模型生成题目：模型的错误会成为标准答案，评测就没有意义了。
这里每题的标准答案都能追溯到 SDE 字段、装配库条目或词条索引，
判分是机械比对，不涉及任何主观判断。

题型与判分方式：
  fact      问某个字段的数值 → 答案里必须出现那个数字
  fit       问某船某槽位装什么 → 答案必须覆盖该槽位的模块名（≥60%）
  class     问某舰种有几艘/有哪些 → 答案里必须出现正确数量
  lore      问某词条是什么      → 答案必须与该词条相关（关键词命中）
  refuse    问资料里没有的东西  → 必须拒答，不能编
  guard     字段存在但 context 缺失 → 必须被护栏拦下
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

SHIP_FIELDS = [
    ("hiSlots", "高能量槽", "个"), ("medSlots", "中能量槽", "个"),
    ("lowSlots", "低能量槽", "个"), ("hp", "结构值", "HP"),
    ("shieldCapacity", "护盾容量", "HP"), ("armorHP", "装甲值", "HP"),
    ("cpuOutput", "CPU 输出", "TF"), ("powerOutput", "能量栅格输出", "MW"),
    ("capacitorCapacity", "电容容量", "GJ"), ("maxVelocity", "最大速度", "m/s"),
]
MOD_FIELDS = [("power", "PG 占用", "MW"), ("cpu", "CPU 占用", "TF"),
              ("volume", "体积", "m³")]

REFUSALS = [
    ("EVE 里怎么建造航空母舰？", "建造系统"),
    ("这个游戏的公司市值多少？", "市值"),
    ("帮我写一首关于星空的诗", "诗"),
    ("现实中航母的排水量是多少？", "排水量"),
    ("下个版本会删掉哪些船？", "下个版本"),
]


def fmt(v) -> str:
    f = float(v)
    return str(int(f)) if f.is_integer() else str(round(f, 1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=99)
    ap.add_argument("--out", default=str(ROOT / "eval" / "questions.jsonl"))
    args = ap.parse_args()
    rng = random.Random(args.seed)

    rows: list[dict] = []
    ships, mods = [], []
    for line in (DATA / "sde_facts.jsonl").open(encoding="utf-8"):
        o = json.loads(line)
        (ships if o.get("category") == "舰船" else mods).append(o)

    # 1) 舰船属性 60 题
    for o in rng.sample(ships, 60):
        a = o.get("attributes", {})
        have = [(k, lab, u) for k, lab, u in SHIP_FIELDS if k in a and a[k]]
        if not have:
            continue
        k, lab, u = rng.choice(have)
        rows.append({"id": f"ship-{len(rows):03d}", "category": "fact",
                     "question": f"{o['name_zh']}的{lab}是多少？",
                     "expect": fmt(a[k]), "unit": u,
                     "kind": "number", "src": f"sde:{o['name_zh']}"})

    # 2) 装备属性 40 题
    for o in rng.sample(mods, 40):
        a = o.get("attributes", {})
        have = [(k, lab, u) for k, lab, u in MOD_FIELDS if k in a and a[k]]
        if not have or not o.get("name_zh"):
            continue
        k, lab, u = rng.choice(have)
        rows.append({"id": f"mod-{len(rows):03d}", "category": "fact",
                     "question": f"{o['name_zh']}的{lab}是多少？",
                     "expect": fmt(a[k]), "unit": u,
                     "kind": "number", "src": f"sde:{o['name_zh']}"})

    # 3) 装配 40 题
    fits = [json.loads(l) for l in (DATA / "fits.jsonl").open(encoding="utf-8")]
    slot_zh = {"hi": "高槽", "med": "中槽", "low": "低槽", "rig": "改装件"}
    # 一艘船可能有多套配置，答案没有唯一解 —— 判分用该船全部配置的模块并集，
    # 只要答的是这艘船真实存在的模块就算对。否则评测在惩罚正确行为。
    union: dict[str, set] = {}
    for f in fits:
        union.setdefault(f["ship_zh"], set()).update(
            it["zh"] for it in f["items"] if it["slot"] in slot_zh)
    picked = rng.sample(fits, min(40, len(fits)))
    for f in picked:
        groups: dict[str, list[str]] = {}
        for it in f["items"]:
            lab = slot_zh.get(it["slot"])
            if lab:
                groups.setdefault(lab, []).append(it["zh"])
        cand = [(lab, v) for lab, v in groups.items() if len(v) >= 2]
        if not cand:
            continue
        lab, items = rng.choice(cand)
        rows.append({"id": f"fit-{len(rows):03d}", "category": "fit",
                     "question": f"{f['ship_zh']}的{lab}装什么？",
                     "expect": items, "kind": "contains",
                     "union": sorted(union.get(f["ship_zh"], set())),
                     "src": f"fit:{f['ship_zh']}"})

    # 4) 舰种 20 题
    import re
    p = ROOT / "canonical" / "02_舰船与装配" / "_topic_舰种索引" / "rewrite.md"
    if p.exists():
        groups = re.findall(r"### (.+?)（(\d+) 艘）", p.read_text(encoding="utf-8"))
        for g, n in rng.sample(groups, min(20, len(groups))):
            rows.append({"id": f"class-{len(rows):03d}", "category": "class",
                         "question": f"{g}有几艘？", "expect": n,
                         "kind": "number", "src": f"class:{g}"})

    # 5) 剧情 20 题
    p = ROOT / "canonical" / "08_剧情与世界观" / "_topic_世界观词条索引" / "rewrite.md"
    if p.exists():
        ents = re.findall(r"### (.+?)\n- 全库出现 \*\*\d+\*\* 次", p.read_text(encoding="utf-8"))
        for e in rng.sample(ents, min(20, len(ents))):
            rows.append({"id": f"lore-{len(rows):03d}", "category": "lore",
                         "question": f"{e}是什么？", "expect": e,
                         "kind": "mentions", "src": f"lore:{e}"})

    # 6) 越界拒答 10 题
    for q, kw in REFUSALS:
        rows.append({"id": f"refuse-{len(rows):03d}", "category": "refuse",
                     "question": q, "expect": kw, "kind": "refuse",
                     "src": "refusal"})
    for q, kw in REFUSALS[:5]:
        rows.append({"id": f"refuse-{len(rows):03d}", "category": "refuse",
                     "question": q.replace("？", "呢"), "expect": kw,
                     "kind": "refuse", "src": "refusal"})

    # 7) 字段缺失 10 题：问 SDE 里没有的字段
    # 要挑 SDE 里真的没有的字段。之前用了信号半径/跃迁速度这些，
    # 它们在 SDE 里存在，结果评测在惩罚「答对了」。
    fake_fields = ["矿石产出速率", "建造时间", "NPC 掉落率", "市场均价", "声望要求"]
    for o in rng.sample(ships, 10):
        lab = rng.choice(fake_fields)
        rows.append({"id": f"guard-{len(rows):03d}", "category": "guard",
                     "question": f"{o['name_zh']}的{lab}是多少？",
                     "expect": "", "kind": "refuse", "src": f"guard:{o['name_zh']}"})

    rng.shuffle(rows)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    from collections import Counter
    c = Counter(r["category"] for r in rows)
    print(f"[eval] 共 {len(rows)} 题 -> {out}")
    for k, v in c.items():
        print(f"  {k:<8} {v}")
    print("\n样例：")
    for r in rows[:4]:
        print(f"  [{r['category']}] {r['question']}  ->  {str(r['expect'])[:60]}")


if __name__ == "__main__":
    main()

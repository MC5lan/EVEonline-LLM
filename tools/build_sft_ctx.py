"""上下文条件化的 SFT 数据（最小证据版）。

核心原则：**context 只放回答所需的那一小段证据。**

第一版把整条装配塞进 context，长度动辄上千 token，只能靠截断——而截断会让
模型看到残缺的资料，学到「猜」。正确做法是让 context 只包含被问到的字段：

    问「巴盖斯级的低槽装什么」
    context：「巴盖斯级『BGS-C5速刷』低槽：信号放大器 II、弹道控制系统 II…」
    答：「低槽装：信号放大器 II、弹道控制系统 II…」

长度从 800 token 降到 80 token，不需要截断，模型学的是「在给定文本里找答案」。

同时保留 15% 反向样本：context 里的数字被改过，答案必须跟着 context 走，
这样学到的是「以检索为准」而不是「以记忆为准」。
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
    ("lowSlots", "低能量槽", "个"), ("rigSlots", "改装件槽", "个"),
    ("hp", "结构值", "HP"), ("shieldCapacity", "护盾容量", "HP"),
    ("armorHP", "装甲值", "HP"), ("cpuOutput", "CPU 输出", "TF"),
    ("powerOutput", "能量栅格输出", "MW"), ("capacitorCapacity", "电容容量", "GJ"),
    ("maxVelocity", "最大速度", "m/s"), ("droneBandwidth", "无人机带宽", "Mbit/s"),
]

MOD_FIELDS = [("power", "PG 占用", "MW"), ("cpu", "CPU 占用", "TF"),
              ("volume", "体积", "m³")]

SLOT_ZH = {"hi": "高槽", "med": "中槽", "low": "低槽",
           "rig": "改装件", "subsystem": "子系统", "drone": "无人机"}

MAX_ITEMS = 6          # 每个槽位最多列几件，超出的用「等 N 件」收尾


def fmt(v):
    f = float(v)
    return int(f) if f.is_integer() else round(f, 1)


def row(ctx: str, q: str, a: str, src: str) -> dict:
    return {"context": ctx, "messages": [{"role": "user", "content": q},
                                         {"role": "assistant", "content": a}],
            "source": src}


SLOT_KEYS = {"hiSlots", "medSlots", "lowSlots", "rigSlots"}


def pick_wrong(rng: random.Random, key: str) -> float:
    """反向样本用的假数值。

    上一版只在真值 ×0.6~1.4 里扰动，模型没见过「和真值毫不相干的数字」，
    于是学成了「记住真值」而不是「照抄 context」。所以这里取全范围随机。
    槽位不能是小数（会露馅），单独取整数。
    """
    if key in SLOT_KEYS:
        return float(rng.randint(1, 12))
    return float(rng.randint(1, 9999))


def from_ships(rng: random.Random, perturb: float) -> list[dict]:
    """问一个属性时，context 只给 3 个属性——既够回答，又逼模型做选择。"""
    out, path = [], DATA / "sde_facts.jsonl"
    if not path.exists():
        return out
    for line in path.open(encoding="utf-8"):
        o = json.loads(line)
        if o.get("category") != "舰船":
            continue
        a, zh, en = o.get("attributes", {}), o.get("name_zh", ""), o.get("name_en", "")
        if not zh:
            continue
        have = [(k, lab, u) for k, lab, u in SHIP_FIELDS if k in a and a[k]]
        if len(have) < 3:
            continue
        for k, lab, u in rng.sample(have, min(3, len(have))):
            others = rng.sample([x for x in have if x[0] != k], min(2, len(have) - 1))
            ctx_items = [(k, lab, u)] + others
            rng.shuffle(ctx_items)
            v = fmt(a[k])
            want = v
            if rng.random() < perturb:
                want = pick_wrong(rng, k)
            parts = []
            for kk, ll, uu in ctx_items:
                val = want if kk == k else fmt(a[kk])
                parts.append(f"{ll} {fmt(val)} {uu}")
            ctx = f"{zh}（{en}）：" + "；".join(parts)
            q = rng.choice([f"{zh}的{lab}是多少？", f"{zh} {lab}多少",
                            f"问一下{zh}的{lab}"])
            out.append(row(ctx, q, f"{zh}的{lab}是 {fmt(want)} {u}。", f"sde:{zh}"))
    return out


def from_modules(rng: random.Random, perturb: float) -> list[dict]:
    out, path = [], DATA / "sde_facts.jsonl"
    if not path.exists():
        return out
    for line in path.open(encoding="utf-8"):
        o = json.loads(line)
        if o.get("category") != "装备":
            continue
        a, zh = o.get("attributes", {}), o.get("name_zh", "")
        if not zh:
            continue
        have = [(k, lab, u) for k, lab, u in MOD_FIELDS if k in a and a[k]]
        if not have:
            continue
        k, lab, u = rng.choice(have)
        v = fmt(a[k])
        want = pick_wrong(rng, k) if rng.random() < perturb else v
        others = [(kk, ll, uu) for kk, ll, uu in have if kk != k][:2]
        parts = [f"{lab} {fmt(want)} {u}"] + [f"{ll} {fmt(a[kk])} {uu}" for kk, ll, uu in others]
        out.append(row(f"{zh}：" + "；".join(parts), f"{zh}的{lab}是多少？",
                       f"{zh}的{lab}是 {fmt(want)} {u}。", f"sde:{zh}"))
    return out


def _slot_text(items: list[str]) -> str:
    if len(items) <= MAX_ITEMS:
        return "、".join(items)
    return "、".join(items[:MAX_ITEMS]) + f" 等 {len(items)} 件"


def from_fits(rng: random.Random, perturb: float) -> list[dict]:
    """问某个槽位时只给那个槽位；问整套时给压缩后的摘要。"""
    out, path = [], DATA / "fits.jsonl"
    if not path.exists():
        return out
    for line in path.open(encoding="utf-8"):
        f = json.loads(line)
        groups: dict[str, list[str]] = {}
        for it in f["items"]:
            lab = SLOT_ZH.get(it["slot"])
            if not lab:
                continue
            q = f"{it['qty']}x " if it.get("qty", 1) > 1 else ""
            groups.setdefault(lab, []).append(q + it["zh"])
        if not groups:
            continue
        ship, fit = f["ship_zh"], f["fit"]

        # 单槽位提问：context 只含该槽位
        for lab, items in groups.items():
            if len(items) < 2:
                continue
            text = _slot_text(items)
            ctx = f"{ship}「{fit}」{lab}：{text}"
            out.append(row(ctx, rng.choice([f"{ship}的{lab}装什么？", f"{ship} {lab}配置"]),
                           f"「{fit}」的{lab}装：{text}。", f"fit:{ship}"))

        # 整套提问：context 用「槽位 + 件数 + 前几件」的摘要，长度可控
        summary = []
        for lab, items in groups.items():
            summary.append(f"{lab} {len(items)} 件（{_slot_text(items)}）")
        ctx = f"{ship}「{fit}」：" + "；".join(summary)
        out.append(row(ctx, rng.choice([f"{ship}怎么配船？", f"给我一套{ship}的装配"]),
                       f"{ship}有一套「{fit}」：" + "；".join(summary) + "。", f"fit:{ship}"))
    return out


def from_multiturn(rng: random.Random) -> list[dict]:
    """多轮：context 只放槽位数字，足够回答全部追问。"""
    out, path = [], DATA / "sde_facts.jsonl"
    if not path.exists():
        return out
    chain = [("hiSlots", "高能量槽"), ("medSlots", "中能量槽"), ("lowSlots", "低能量槽")]
    for line in path.open(encoding="utf-8"):
        o = json.loads(line)
        if o.get("category") != "舰船":
            continue
        a, zh = o.get("attributes", {}), o.get("name_zh", "")
        have = [(k, lab) for k, lab in chain if k in a and a[k]]
        if len(have) < 3 or not zh:
            continue
        ctx = f"{zh}：" + "；".join(f"{lab} {int(a[k])} 个" for k, lab in have)
        msgs = [{"role": "user", "content": f"{zh}有几个{have[0][1]}？"},
                {"role": "assistant", "content": f"{int(a[have[0][0]])} 个。"}]
        for k, lab in have[1:]:
            msgs.append({"role": "user",
                         "content": rng.choice([f"那{lab}呢？", f"{lab}呢"])})
            msgs.append({"role": "assistant", "content": f"{int(a[k])} 个。"})
        out.append({"context": ctx, "messages": msgs, "source": f"multi:{zh}"})
    return out


def from_classes(rng: random.Random) -> list[dict]:
    out = []
    p = ROOT / "canonical" / "02_舰船与装配" / "_topic_舰种索引" / "rewrite.md"
    if not p.exists():
        return out
    import re
    for m in re.finditer(r"### (.+?)（(\d+) 艘）\n(.+)", p.read_text(encoding="utf-8")):
        group, n, body = m.group(1), m.group(2), m.group(3)
        names = [s.split("（")[0] for s in body.split("；") if s.strip()]
        text = "、".join(names[:10]) + (f" 等 {len(names)} 艘" if len(names) > 10 else "")
        ctx = f"{group} 共 {n} 艘：{text}"
        out.append(row(ctx, f"{group}有哪些船？", f"{group}共 {n} 艘：{text}。", f"class:{group}"))
    return out


def from_refusals() -> list[dict]:
    items = [
        ("EVE 里怎么建造航空母舰？", "资料里没有建造系统的内容，无法回答。"),
        ("帮我写一首关于星空的诗", "这不在我的资料范围内。"),
        ("下个版本会出什么新船？", "数据截止到 SDE build 3662168，之后的变化不知道。"),
    ]
    return [row("深渊纤维共分七级，宁静为入门级。", q, a, "refusal") for q, a in items]


def from_missing(rng: random.Random) -> list[dict]:
    """字段缺失样本：context 里没有被问的那一项，正确回答是「资料里没有」。

    没有这类样本，模型在资料缺失时不会拒答，而是从邻近字段挪用数值
    （实测它把「最大速度 190 m/s」当成了护盾容量）。
    """
    out, path = [], DATA / "sde_facts.jsonl"
    if not path.exists():
        return out
    for line in path.open(encoding="utf-8"):
        o = json.loads(line)
        if o.get("category") not in ("舰船", "装备"):
            continue
        a, zh = o.get("attributes", {}), o.get("name_zh", "")
        if not zh:
            continue
        fields = SHIP_FIELDS if o["category"] == "舰船" else MOD_FIELDS
        have = [(k, lab, u) for k, lab, u in fields if k in a and a[k]]
        if len(have) < 3:
            continue
        # 关键：拿掉一个本来存在、也有值的字段，而不是去问 SDE 里天生没有的字段。
        # 后者学出来的是「这几艘船没有这个属性」，前者才是「这里没写，就说没有」。
        _k, lab, _u = rng.choice(have)
        shown = rng.sample([x for x in have if x[0] != _k], min(2, len(have) - 1))
        ctx = f"{zh}：" + "；".join(f"{ll} {fmt(a[kk])} {uu}" for kk, ll, uu in shown)
        out.append(row(ctx, f"{zh}的{lab}是多少？",
                       f"资料里没有 {zh} 的{lab}。", f"miss:{zh}"))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--perturb", type=float, default=0.4)
    ap.add_argument("--val-ratio", type=float, default=0.03)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    parts = {
        "ships": from_ships(rng, args.perturb),
        "modules": from_modules(rng, args.perturb),
        "fits": from_fits(rng, args.perturb),
        "multi": from_multiturn(rng),
        "classes": from_classes(rng),
        "missing": from_missing(rng),
        "refusals": from_refusals(),
    }
    for k, v in parts.items():
        print(f"  {k:<10} {len(v):>6} 条")

    rows = [r for v in parts.values() for r in v]
    rng.shuffle(rows)
    n_val = max(50, int(len(rows) * args.val_ratio))
    val, train = rows[:n_val], rows[n_val:]
    for name, data in (("sft.jsonl", train), ("sft_val.jsonl", val)):
        with (DATA / name).open("w", encoding="utf-8") as f:
            for r in data:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"[sft] {name}: {len(data):,} 条")

    print("\n样例：")
    for r in train[:3]:
        print("  ctx:", r["context"][:100])
        print("  Q:", r["messages"][0]["content"])
        print("  A:", r["messages"][1]["content"][:100])
        print()


if __name__ == "__main__":
    main()

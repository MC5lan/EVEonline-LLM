"""从结构化资产自动生成 SFT 问答对。

原则：**答案只从数据来，不自由发挥。**
每一条问答的答案都能追溯到 SDE 卡片、装配库、舰种索引或剧情词条，
这样 SFT 教给模型的是「怎么把事实说清楚」，而不是「记住更多事实」。

生成来源与配比：
  舰船属性   7,591 张卡 → 每艘船 4~6 个属性问题
  装备属性   约 4,000 件  → PG/CPU/槽位
  装配       359 套      → 怎么配、用什么模块
  舰种       48 组       → 某舰种有哪些船
  剧情       71 条       → 某势力/星域是什么
  拒答       若干         → 资料里没有的问题该怎么说不知道
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from sft_extra import from_fit_multiturn, from_multiturn

DATA = ROOT / "data"

SHIP_ATTRS = [
    ("hiSlots", "高能量槽", "个"),
    ("medSlots", "中能量槽", "个"),
    ("lowSlots", "低能量槽", "个"),
    ("rigSlots", "改装件槽", "个"),
    ("hp", "结构值", "HP"),
    ("shieldCapacity", "护盾容量", "HP"),
    ("armorHP", "装甲值", "HP"),
    ("cpuOutput", "CPU 输出", "TF"),
    ("powerOutput", "能量栅格输出", "MW"),
    ("capacitorCapacity", "电容容量", "GJ"),
    ("maxVelocity", "最大速度", "m/s"),
    ("signatureRadius", "信号半径", "m"),
    ("droneBandwidth", "无人机带宽", "Mbit/s"),
    ("capacity", "货舱容量", "m³"),
    ("mass", "质量", "kg"),
]

MOD_ATTRS = [
    ("power", "PG 占用", "MW"),
    ("cpu", "CPU 占用", "TF"),
    ("slots", "占用的槽位", "个"),
    ("volume", "体积", "m³"),
]

# 资料里没有的问题：教模型说「不知道」，而不是编一个
REFUSALS = [
    ("EVE 里怎么建造航空母舰？", "我的资料里没有建造系统的内容，无法回答。"),
    ("这个游戏的开发公司股票怎么样？", "这不在我的资料范围内，我只掌握 EVE 的舰船、装配和玩法资料。"),
    ("帮我写一首关于星空的诗", "这不是我的专长，我的资料集中在 EVE 的玩法与数据上。"),
    ("现实中航母的排水量是多少？", "资料里没有现实世界的内容，我只能回答 EVE 相关的问题。"),
    ("下个版本会出什么新船？", "我的数据截止到 SDE build 3662168，之后的版本变化我不知道。"),
]


def qa(q: str, a: str, src: str) -> dict:
    return {"messages": [{"role": "user", "content": q},
                         {"role": "assistant", "content": a}],
            "source": src}


def from_ships(rng: random.Random) -> list[dict]:
    out = []
    path = DATA / "sde_facts.jsonl"
    if not path.exists():
        return out
    for line in path.open(encoding="utf-8"):
        o = json.loads(line)
        if o.get("category") != "舰船":
            continue
        a = o.get("attributes", {})
        zh, en = o.get("name_zh", ""), o.get("name_en", "")
        if not zh:
            continue
        # 逐条属性问，最多问 6 个（避免同一艘船刷太多条）
        cand = [(k, lab, u) for k, lab, u in SHIP_ATTRS if k in a and a[k]]
        rng.shuffle(cand)
        for k, lab, u in cand[:6]:
            v = a[k]
            v = int(v) if float(v).is_integer() else round(float(v), 1)
            qs = [f"{zh}的{lab}是多少？", f"{zh} {lab}多少", f"问一下{zh}的{lab}"]
            out.append(qa(rng.choice(qs),
                          f"{zh}（{en}）的{lab}是 {v} {u}。",
                          f"sde:{zh}"))
        # 综合一问
        parts = []
        for k, lab, u in SHIP_ATTRS[:5]:
            if k in a and a[k]:
                v = a[k]
                v = int(v) if float(v).is_integer() else round(float(v), 1)
                parts.append(f"{lab} {v} {u}")
        if parts:
            out.append(qa(f"介绍一下{zh}的基本属性",
                          f"{zh}（{en}）：" + "；".join(parts) + "。",
                          f"sde:{zh}"))
    return out


def from_modules(rng: random.Random) -> list[dict]:
    out = []
    path = DATA / "sde_facts.jsonl"
    if not path.exists():
        return out
    for line in path.open(encoding="utf-8"):
        o = json.loads(line)
        if o.get("category") != "装备":
            continue
        a = o.get("attributes", {})
        zh = o.get("name_zh", "")
        if not zh:
            continue
        pairs = [(k, lab, u) for k, lab, u in MOD_ATTRS if k in a and a[k]]
        if not pairs:
            continue
        k, lab, u = rng.choice(pairs)
        v = a[k]
        v = int(v) if float(v).is_integer() else round(float(v), 1)
        out.append(qa(f"{zh}的{lab}是多少？",
                      f"{zh}的{lab}是 {v} {u}。", f"sde:{zh}"))
    return out


def from_fits(rng: random.Random) -> list[dict]:
    out = []
    path = DATA / "fits.jsonl"
    if not path.exists():
        return out
    by_ship: dict[str, list[dict]] = {}
    for line in path.open(encoding="utf-8"):
        f = json.loads(line)
        by_ship.setdefault(f["ship_zh"], []).append(f)

    slot_zh = {"hi": "高槽", "med": "中槽", "low": "低槽",
               "rig": "改装件", "subsystem": "子系统", "drone": "无人机"}
    for ship, fits in by_ship.items():
        for f in fits:
            groups: dict[str, list[str]] = {}
            for it in f["items"]:
                lab = slot_zh.get(it["slot"])
                if not lab:
                    continue
                q = f"{it['qty']}x " if it.get("qty", 1) > 1 else ""
                groups.setdefault(lab, []).append(q + it["zh"])
            if not groups:
                continue
            body = "；".join(f"{k}：{'、'.join(v)}" for k, v in groups.items())
            qs = [f"{ship}怎么配船？", f"{ship}有什么配置方案？",
                  f"给我一套{ship}的装配"]
            out.append(qa(rng.choice(qs),
                          f"{ship}有一套「{f['fit']}」：{body}。",
                          f"fit:{ship}"))
            # 只问某个槽位
            for lab, items in groups.items():
                if len(items) >= 2:
                    out.append(qa(f"{ship}的{lab}装什么？",
                                  f"「{f['fit']}」的{lab}装：{'、'.join(items)}。",
                                  f"fit:{ship}"))
    return out


def from_classes(rng: random.Random) -> list[dict]:
    out = []
    p = ROOT / "canonical" / "02_舰船与装配" / "_topic_舰种索引" / "rewrite.md"
    if not p.exists():
        return out
    import re
    text = p.read_text(encoding="utf-8")
    for m in re.finditer(r"### (.+?)（(\d+) 艘）\n(.+)", text):
        group, n, body = m.group(1), m.group(2), m.group(3)
        ships = [s.split("（")[0] for s in body.split("；") if s.strip()]
        if not ships:
            continue
        sample = "、".join(ships[:8]) + ("等" if len(ships) > 8 else "")
        out.append(qa(f"{group}有哪些船？",
                      f"{group}共 {n} 艘，包括{sample}。", f"class:{group}"))
        out.append(qa(f"{group}有几艘？", f"{group}共 {n} 艘。", f"class:{group}"))
    return out


def from_lore(rng: random.Random) -> list[dict]:
    out = []
    p = ROOT / "canonical" / "08_剧情与世界观" / "_topic_世界观词条索引" / "rewrite.md"
    if not p.exists():
        return out
    import re
    text = p.read_text(encoding="utf-8")
    for m in re.finditer(r"### (.+?)\n- 全库出现 \*\*(\d+)\*\* 次\n(?:- 主要出现在：(.+?)\n)?(?:- 原文：「(.+?)」)?", text):
        name, cnt, docs, quote = m.group(1), m.group(2), m.group(3), m.group(4)
        if not quote:
            continue
        out.append(qa(f"{name}是什么？",
                      f"{quote}（该词在剧情语料中出现 {cnt} 次）",
                      f"lore:{name}"))
    return out


def from_refusals(rng: random.Random) -> list[dict]:
    return [qa(q, a, "refusal") for q, a in REFUSALS]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--val-ratio", type=float, default=0.03)
    ap.add_argument("--max-per-ship", type=int, default=8)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    parts = {
        "ships": from_ships(rng),
        "modules": from_modules(rng),
        "fits": from_fits(rng),
        "classes": from_classes(rng),
        "lore": from_lore(rng),
        "multi": from_multiturn(rng),
        "fitmulti": from_fit_multiturn(rng),
        "refusals": from_refusals(rng),
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

    # 抽样看一眼
    print("\n样例：")
    for r in train[:3] + train[-3:]:
        print("  Q:", r["messages"][0]["content"])
        print("  A:", r["messages"][1]["content"][:90])
        print()


if __name__ == "__main__":
    main()

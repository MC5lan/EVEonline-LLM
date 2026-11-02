"""把官方 SDE 的 types.jsonl 渲染成可检索的"卡片"。

为什么需要这一步：
SDE 是结构化字段，向量检索读不懂 {"_key": 645, "dogmaAttributes": [...]}。
但把它渲染成一段自然语言——"多米尼克斯级，盖伦特战列舰，高能量槽 6…"——
它就能被 BM25 和向量同时命中，而且数值是精确的。

字段取舍（关键设计）：
  * 属性只渲染常用的一批（槽位/防御/电容/电子/机动/无人机），约 20 个。
    全部渲染会塞进几十个噪声字段，把真正有用的数值淹掉。
  * 完整属性仍然保留在 data/sde_facts.jsonl 里，供精确查询（SQLite/查表）使用。
    检索要"好读"，事实要"完整"，两者分开。

用法：
  python tools/build_sde_cards.py --sde data/extracted/静态数据/静态数据 --out data/sde_cards.jsonl
  python tools/build_sde_cards.py --sde ... --categories Ship --limit 5 --preview
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

# 渲染顺序就是阅读顺序：先身份，再槽位，再防御，最后机动
ATTR_SPEC = [
    ("hiSlots", "高能量槽", "{}"),
    ("medSlots", "中能量槽", "{}"),
    ("lowSlots", "低能量槽", "{}"),
    ("rigSlots", "改装件槽", "{}"),
    ("launcherSlotsLeft", "发射器槽", "{}"),
    ("hp", "结构值", "{} HP"),
    ("shieldCapacity", "护盾容量", "{} HP"),
    ("armorHP", "装甲值", "{} HP"),
    ("cpuOutput", "CPU 输出", "{} TF"),
    ("powerOutput", "能量栅格输出", "{} MW"),
    ("capacitorCapacity", "电容容量", "{} GJ"),
    ("droneBandwidth", "无人机带宽", "{} Mbit/s"),
    ("droneCapacity", "无人机挂舱", "{} m³"),
    ("maxVelocity", "最大速度", "{} m/s"),
    ("signatureRadius", "信号半径", "{} m"),
    ("maxTargetRange", "锁定距离", "{} m"),
    ("scanResolution", "扫描分辨率", "{} mm"),
    ("maxLockedTargets", "最大锁定目标", "{}"),
    ("warpSpeedMultiplier", "跃迁速度", "{} AU/s"),
    ("capacity", "货舱容量", "{} m³"),
    ("mass", "质量", "{} kg"),
    ("techLevel", "科技等级", "T{}"),
    ("metaLevel", "衍生等级", "{}"),
]

TARGET_CATEGORIES = {"Ship", "Module", "Drone", "Charge", "Skill",
                     "Implant", "Subsystem", "Fighter", "Structure"}


def loc(v) -> str:
    """SDE 的新格式里 name/description 是 {lang: text} 字典。"""
    if isinstance(v, dict):
        return (v.get("zh") or v.get("en") or "").strip()
    return (v or "").strip()


def load_jsonl(path: Path, key: str = "_key") -> dict:
    out = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            out[o[key]] = o
    return out


def fmt(v: float) -> str:
    if v == int(v):
        return str(int(v))
    return f"{v:.2f}".rstrip("0").rstrip(".")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sde", required=True, help="解压后的 SDE 目录")
    ap.add_argument("--out", default="data/sde_cards.jsonl")
    ap.add_argument("--facts-out", default="data/sde_facts.jsonl")
    ap.add_argument("--categories", nargs="*", default=sorted(TARGET_CATEGORIES))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--preview", action="store_true", help="只打印，不写文件")
    args = ap.parse_args()

    sde = Path(args.sde)
    cats = load_jsonl(sde / "categories.jsonl")
    groups = load_jsonl(sde / "groups.jsonl")
    dogma = load_jsonl(sde / "dogmaAttributes.jsonl")

    wanted_cats = set(args.categories)
    print(f"[sde] 目标分类: {sorted(wanted_cats)}")

    # 第一遍：挑出目标 type
    types: dict[int, dict] = {}
    with (sde / "types.jsonl").open(encoding="utf-8") as f:
        for line in f:
            if len(line) < 40 or "_key" not in line:
                continue
            o = json.loads(line)
            g = groups.get(o.get("groupID"))
            if not g:
                continue
            c = cats.get(g.get("categoryID"))
            if not c or c.get("name", {}).get("en") not in wanted_cats:
                continue
            if not o.get("published", True):
                continue
            types[o["_key"]] = o
            if args.limit and len(types) >= args.limit:
                break
    print(f"[sde] 命中 {len(types):,} 个 type")

    # 第二遍：只保留这些 type 的属性（避免把 27MB 全塞进内存）
    attr_name = {aid: a.get("name", "") for aid, a in dogma.items()}
    attrs: dict[int, dict[str, float]] = {}
    with (sde / "typeDogma.jsonl").open(encoding="utf-8") as f:
        for line in f:
            if "_key" not in line:
                continue
            o = json.loads(line)
            tid = o["_key"]
            if tid not in types:
                continue
            d = {}
            for a in o.get("dogmaAttributes", []):
                n = attr_name.get(a["attributeID"])
                if n:
                    d[n] = a["value"]
            attrs[tid] = d
    print(f"[sde] 属性覆盖 {len(attrs):,} 个 type")

    cards, facts = [], []
    for tid, o in types.items():
        g = groups.get(o.get("groupID"), {})
        c = cats.get(g.get("categoryID"), {})
        name_zh, name_en = loc(o.get("name")), (o.get("name") or {}).get("en", "")
        desc = loc(o.get("description"))

        vals = dict(attrs.get(tid, {}))
        # types.jsonl 的顶层字段（capacity/mass/volume）不在 dogmaAttributes 里。
        # 只读 dogma 会把所有舰船的「货舱容量」漏掉，导致配装类判断出错
        # （比如误判「备用无人机放不下」）。
        for k in ("capacity", "mass", "volume"):
            if k not in vals and o.get(k) is not None:
                vals[k] = o[k]

        parts = []
        for key, label, tmpl in ATTR_SPEC:
            v = vals.get(key)
            if v is None:
                continue
            if v == 0 and key not in ("metaLevel",):
                continue
            parts.append(f"{label} {tmpl.format(fmt(v))}")

        head = f"{name_zh}（{name_en}）" if name_zh and name_zh != name_en else (name_en or name_zh)
        meta = f"分类：{loc(c.get('name'))} > {loc(g.get('name'))}"
        # 属性必须排在描述前面。检索/prompt 拼装会按 chunk_chars 截断，
        # 描述动辄三四百字，放在前面就会把槽位和数值整个挤掉——
        # 而对 EVE 来说恰恰是数值才是答案。
        body = f"{head}\n{meta}"
        if parts:
            body += "\n属性：" + "；".join(parts)
        if desc:
            body += f"\n描述：{desc}"

        cards.append({"typeID": tid, "name": name_zh or name_en, "text": body})
        facts.append({"typeID": tid, "name_zh": name_zh, "name_en": name_en,
                      "category": loc(c.get("name")), "group": loc(g.get("name")),
                      "attributes": vals})

    if args.preview:
        for c in cards[:5]:
            print("\n" + "=" * 50)
            print(c["text"][:600])
        return

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for c in cards:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    fout = Path(args.facts_out)
    fout.parent.mkdir(parents=True, exist_ok=True)
    with fout.open("w", encoding="utf-8") as f:
        for c in facts:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    avg = sum(len(c["text"]) for c in cards) / max(1, len(cards))
    print(f"[sde] 卡片 {len(cards):,} 张，平均 {avg:.0f} 字 -> {out}")
    print(f"[sde] 事实 {len(facts):,} 条 -> {fout}")


if __name__ == "__main__":
    main()

"""交叉验证：把攻略文本里的数值断言和 SDE 对齐。

规则（已确认）：**SDE 为准**。冲突的文本不删除，标记为「经验/过时」并降权。
删除会丢掉版本历史，而版本历史本身也是 EVE 知识的一部分——
"当年 6 高槽"这种信息，对理解一次改版是有价值的。

做法刻意保守：
  1. 只有一段里**恰好提到一艘船**时才检查（多艘船无法确定断言归属）
  2. 断言必须出现在船名之后 400 字以内（中文是后置定语习惯）
  3. 只认明确的槽位写法，宁可漏报不可误报

产出：
  data/conflicts.jsonl   每条冲突：来源、块号、断言、SDE 值

用法：
  python tools/crosscheck.py
  python tools/crosscheck.py --limit 2000
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 槽位断言的几种常见写法。
#
# 负向断言 (?!\s*[xX×]) 是关键：EVE 攻略里「高槽: 2x 小型激光器」说的是
# 装了 2 个武器，不是船有 2 个高槽。第一版没排除这种写法，
# 抽查 7 条"冲突"全是这类误报，精度接近 0。
PATTERNS = [
    (re.compile(r"(?:高能量槽|高能槽|高槽)\s*[:：]?\s*(\d+)(?!\s*[xX×])"), "hiSlots"),
    (re.compile(r"(?:中能量槽|中能槽|中槽)\s*[:：]?\s*(\d+)(?!\s*[xX×])"), "medSlots"),
    (re.compile(r"(?:低能量槽|低能槽|低槽)\s*[:：]?\s*(\d+)(?!\s*[xX×])"), "lowSlots"),
    (re.compile(r"(\d+)\s*(?:个)?\s*(?:高能量槽|高能槽|高槽)"), "hiSlots"),
    (re.compile(r"(\d+)\s*(?:个)?\s*(?:中能量槽|中能槽|中槽)"), "medSlots"),
    (re.compile(r"(\d+)\s*(?:个)?\s*(?:低能量槽|低能槽|低槽)"), "lowSlots"),
]
COMBO = re.compile(r"(\d+)\s*高\s*(\d+)\s*中\s*(\d+)\s*低")

# 目录页：一堆 "...... 页码"，里面的数字全是页码
TOC = re.compile(r"[.．]{4,}")
# 装配清单特征：反复出现 "2x模块名"
FIT_ITEM = re.compile(r"\d+\s*[xX×]")

LABEL = {"hiSlots": "高能量槽", "medSlots": "中能量槽", "lowSlots": "低能量槽"}


def load_facts(p: Path) -> dict[int, dict]:
    out = {}
    with p.open(encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            if o.get("category") == "舰船":
                out[int(o["typeID"])] = o
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--facts", default=str(ROOT / "data" / "sde_facts.jsonl"))
    ap.add_argument("--chunks", default=str(ROOT / "index" / "chunks.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "data" / "conflicts.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    import sys
    sys.path.insert(0, str(ROOT))
    from rag.entities import EntityIndex

    ships = load_facts(Path(args.facts))
    ent = EntityIndex()
    # 只保留舰船实体，避免把装备名当成船名做归属
    ship_names = {k: v for k, v in ent.items.items() if int(v.get("typeID") or 0) in ships}
    ent.items = ship_names
    ent.max_len = max((len(k) for k in ship_names), default=0)
    print(f"[check] 舰船实体 {len(ship_names):,} 个，SDE 舰船 {len(ships):,} 艘")

    rows = []
    with open(args.chunks, encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
            if args.limit and len(rows) >= args.limit:
                break
    print(f"[check] 待检查块 {len(rows):,}")

    conflicts = []
    checked = 0
    skipped_toc = skipped_fit = 0
    for r in rows:
        if r.get("tier") == "官方":
            continue
        text = r["text"]
        # 目录页与装配清单不参与断言检查：
        # 前者的数字是页码，后者是件数，都不是船体槽位。
        if TOC.search(text):
            skipped_toc += 1
            continue
        if len(FIT_ITEM.findall(text)) >= 3:
            skipped_fit += 1
            continue
        found = ent.find(text)
        if len(found) != 1:
            continue
        e = found[0]
        tid = int(e["typeID"])
        f = ships.get(tid)
        if not f:
            continue
        attrs = f.get("attributes", {})

        # 断言必须出现在船名之后
        pos = text.find(e["matched"])
        tail = text[pos:] if pos >= 0 else text
        checked += 1

        claims: dict[str, list[int]] = {}
        for pat, key in PATTERNS:
            for m in pat.finditer(tail[:400]):
                claims.setdefault(key, []).append(int(m.group(1)))
        for m in COMBO.finditer(tail[:400]):
            claims.setdefault("hiSlots", []).append(int(m.group(1)))
            claims.setdefault("medSlots", []).append(int(m.group(2)))
            claims.setdefault("lowSlots", []).append(int(m.group(3)))

        for key, vals in claims.items():
            actual = attrs.get(key)
            if actual is None:
                continue
            actual = int(actual)
            for v in vals:
                if v != actual:
                    conflicts.append({
                        "source": r.get("source"), "pos": r.get("pos"),
                        "typeID": tid, "name": f.get("name_zh"),
                        "field": LABEL[key], "claimed": v, "actual": actual,
                        "tier": r.get("tier"), "year": r.get("year", ""),
                        "snippet": tail[:120].replace("\n", " "),
                    })

    # 同一条断言会被多个正则命中（"2 高槽" 与 "高槽 2" 两种写法），
    # 按 (来源,块,字段,断言值) 去重，否则同一处会重复报好几遍。
    uniq: dict[tuple, dict] = {}
    for c in conflicts:
        k = (c["source"], c["pos"], c["field"], c["claimed"], c["actual"])
        uniq.setdefault(k, c)
    conflicts = list(uniq.values())

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for c in conflicts:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"[check] 检查了 {checked:,} 个含单船的块，发现冲突 {len(conflicts):,} 条 -> {out}")
    print(f"[check] 跳过目录页 {skipped_toc:,} 块、装配清单 {skipped_fit:,} 块")

    if conflicts:
        from collections import Counter
        by_src = Counter(c["source"] for c in conflicts)
        print("\n冲突最多的文档：")
        for name, n in by_src.most_common(8):
            print(f"  {n:4}  {name}")
        print("\n样例：")
        for c in conflicts[:5]:
            print(f"  {c['name']} {c['field']}: 文本说 {c['claimed']}，SDE 是 {c['actual']}"
                  f"  <- {c['source']}#{c['pos']}")


if __name__ == "__main__":
    main()

"""从 SDE 事实表 + 社区别名表，构建实体词表（用于查询里的专有名词锁定）。

为什么需要它：
向量检索分不清「多米尼克斯级」和「多米尼克斯级海军型」——两者字面几乎相同，
embedding 也几乎相同。但玩家问的是具体那艘船，答案的槽位和抗性完全不同。
这一层用规则做精确锁定：query 里出现哪个名字，就把它锚到 typeID。

产出 data/entities.jsonl，每行一个可匹配的写法：
  {"name": "多米尼克斯级", "typeID": 645, "zh": "多米尼克斯级", "en": "Dominix", "kind": "zh"}

用法：
  python tools/build_entities.py
  python tools/build_entities.py --aliases "D:/new/.../t2_aliases.jsonl"
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ALIASES = Path(r"D:\new\导出_数据库与知识库_20260923\数据库\02_EVE_SDE结构化数据\t2_aliases.jsonl")
DEFAULT_SHIPS = Path(r"D:\new\导出_数据库与知识库_20260923\数据库\06_中英对照字典表\ships_舰船561艘英汉对照.csv")

# 太泛的词不该被当成实体，否则任何一句话都会"命中"某个物品
STOP = {"舰船", "装备", "无人机", "弹药", "技能", "蓝图", "材料", "商品",
        "ship", "module", "drone", "skill", "test", "system"}

MIN_CJK = 2
MIN_ASCII = 3


def norm(s: str) -> str:
    return (s or "").strip().lower()


def good(name: str) -> bool:
    n = norm(name)
    if not n or n in STOP:
        return False
    if n.isascii():
        return len(n) >= MIN_ASCII
    return len(n) >= MIN_CJK


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--facts", default=str(ROOT / "data" / "sde_facts.jsonl"))
    ap.add_argument("--aliases", default=str(DEFAULT_ALIASES))
    ap.add_argument("--ships", default=str(DEFAULT_SHIPS))
    ap.add_argument("--out", default=str(ROOT / "data" / "entities.jsonl"))
    args = ap.parse_args()

    canonical: dict[int, tuple[str, str]] = {}
    entries: list[dict] = []

    facts = Path(args.facts)
    if not facts.exists():
        raise SystemExit(f"缺少 {facts}，先跑 tools/build_sde_cards.py")

    with facts.open(encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            tid = int(o["typeID"])
            zh, en = o.get("name_zh", ""), o.get("name_en", "")
            canonical[tid] = (zh, en)
            for name, kind in ((zh, "zh"), (en, "en")):
                if good(name):
                    entries.append({"name": name, "typeID": tid, "zh": zh, "en": en, "kind": kind})

    n_base = len(entries)

    aliases = Path(args.aliases)
    n_alias = 0
    if aliases.exists():
        with aliases.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except json.JSONDecodeError:
                    continue
                tid = int(o.get("typeID") or 0)
                name = o.get("名称", "")
                if not good(name):
                    continue
                zh, en = canonical.get(tid, ("", ""))
                entries.append({"name": name, "typeID": tid,
                                "zh": zh or name, "en": en, "kind": "alias"})
                n_alias += 1
    else:
        print(f"[warn] 别名表不存在，跳过: {aliases}")

    ships = Path(args.ships)
    n_ship = 0
    if ships.exists():
        with ships.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                try:
                    tid = int(row["typeID"])
                except (KeyError, ValueError):
                    continue
                zh, en = row.get("name_zh", ""), row.get("name_en", "")
                for name, kind in ((zh, "zh"), (en, "en")):
                    if good(name) and tid not in canonical:
                        entries.append({"name": name, "typeID": tid, "zh": zh, "en": en, "kind": kind})
                        n_ship += 1

    # 去重：同一个写法只留一条（先到先得，SDE 官方名优先）
    seen: dict[str, dict] = {}
    for e in entries:
        k = norm(e["name"])
        if k not in seen:
            seen[k] = e

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for e in seen.values():
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    lens = [len(k) for k in seen]
    print(f"[entities] SDE {n_base} + 别名 {n_alias} + 补充舰船 {n_ship}")
    print(f"[entities] 去重后 {len(seen):,} 个可匹配写法，"
          f"最长 {max(lens)} 字，最短 {min(lens)} 字 -> {out}")


if __name__ == "__main__":
    main()

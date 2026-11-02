"""生成「舰种索引」：按 group 归类全部舰船。

用途：用户问「无畏级有几个高槽」时，问的其实不是某艘船，而是一个舰种。
没有这张表，检索只能按词面捞到某一艘无畏舰，答案看着对、其实答非所问。

所有数据来自 SDE，分组也用 SDE 的 group 字段，不自造分类。
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SLOT_KEYS = [("hiSlots", "高"), ("medSlots", "中"), ("lowSlots", "低"),
             ("rigSlots", "改装")]


def main() -> None:
    rows = []
    with (ROOT / "data" / "sde_facts.jsonl").open(encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            if o.get("category") != "舰船":
                continue
            a = o.get("attributes", {})
            slots = "/".join(str(int(a.get(k, 0) or 0)) for k, _ in SLOT_KEYS)
            rows.append((o.get("group", "其他"), o.get("name_zh", ""),
                         o.get("name_en", ""), slots, o.get("typeID")))

    by_group: dict[str, list] = defaultdict(list)
    for g, zh, en, slots, tid in rows:
        by_group[g].append((zh, en, slots, tid))

    out = [
        "---",
        "id: canon-ship-class",
        "title: 舰种索引（按 SDE 分组）",
        "domain: 02_舰船与装配",
        "subdomain: ",
        "type: canonical",
        "status: drafted",
        "sde_build: 3662168 / 2026-10-30",
        "verified: 2026-11-01",
        "---",
        "",
        "# 舰种索引（按 SDE 分组）",
        "",
        f"{len(rows)} 艘舰船，按 SDE 的舰种分组。"
        "问「某个舰种有多少槽」时看这里——单个船的数字不代表整个舰种。",
        "",
        "槽位格式：高/中/低/改装。",
        "",
    ]
    for g in sorted(by_group, key=lambda x: -len(by_group[x])):
        ships = by_group[g]
        # 标题和名单必须在同一段：切块按空行分段，中间留空行会把标题和
        # 名单拆到两个块里，标题块太小、名单块又缺少舰种名，两个都检索不准。
        body = "；".join(f"{zh}（{en}）{slots}" for zh, en, slots, tid
                        in sorted(ships, key=lambda x: x[0]))
        out += [f"### {g}（{len(ships)} 艘）", body, ""]

    d = ROOT / "canonical" / "02_舰船与装配" / "_topic_舰种索引"
    d.mkdir(parents=True, exist_ok=True)
    (d / "source.md").write_text("（本条目由 SDE 舰船分组生成）\n", encoding="utf-8")
    (d / "meta.yaml").write_text(
        "\n".join(["title: 舰种索引（按 SDE 分组）", "domain: 02_舰船与装配",
                   "subdomain: ", "origin: SDE sde_facts.jsonl",
                   f"chars: {len(rows)}", "status: drafted"]) + "\n", encoding="utf-8")
    body = "\n".join(out).rstrip() + "\n"
    (d / "rewrite.md").write_text(body, encoding="utf-8")

    print(f"[class] {len(rows)} 艘 / {len(by_group)} 个舰种 -> {len(body):,} 字")
    for g in sorted(by_group, key=lambda x: -len(by_group[x]))[:8]:
        print(f"  {g:<14} {len(by_group[g]):>3} 艘")


if __name__ == "__main__":
    main()

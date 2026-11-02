"""用 SDE 校订《EVE 缩写映射字典》。

原表把社区讹传当成正式译名，甚至把两艘不同的船合并成一条。
这里逐条对照 SDE 的实际中文名，产出「原写法 / 字典声称 / SDE 实际」三列表，
并把原表标为废弃。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PAIRS = [
    ("审判 / 奥普斯", "Prophecy"),
    ("伊米卡斯", "Ishtar"),
    ("灾难 / 大和", "Drake"),
    ("万王宝座 / WW", "Widow"),
    ("地狱天使 / ABD", "Armageddon"),
    ("狞獾 / 螳螂", "Catalyst"),
    ("乌鸦 / 海鸟 / Crows", "Crow"),
    ("巨鸟", "Raptor"),
    ("弥洱米顿 / 小米", "Maelstrom"),
    ("毒蜥", "Gila"),
    ("多米 / 暴龙", "Dominix"),
    ("万王宝座", "Megathron"),
    ("剑齿虎 / Saber", "Sabre"),
    ("异端", "Heretic"),
]


def main() -> None:
    facts = {}
    with open(ROOT / "data" / "sde_facts.jsonl", encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            if o.get("name_en"):
                facts[o["name_en"]] = o

    rows = []
    for alias, en in PAIRS:
        o = facts.get(en)
        if o:
            rows.append((alias, en, o.get("name_zh", ""), o.get("group", "")))
        else:
            rows.append((alias, en, "—", "SDE 无此英文名"))

    out = [
        "---",
        "id: canon-glossary-01",
        "title: EVE 缩写映射字典（原表已废弃）",
        "domain: 08_剧情与世界观",
        "subdomain: ",
        "type: canonical",
        "status: drafted",
        "sde_build: 3662168 / 2026-10-30",
        "verified: 2026-11-01",
        "---",
        "",
        "# EVE 缩写映射字典（原表已废弃）",
        "",
        "## 结论",
        "",
        "原文档的舰船译名对照**不可用**：大量条目把社区讹传当成正式译名，",
        "还有条目把两艘不同的船合并成一条。用它训练，模型会把「审判」学成先知级、",
        "把「地狱天使」学成末日沙场级。",
        "",
        "正确的舰船译名见 02_舰船与装配/_topic_舰船译名对照/rewrite.md（426 艘，全部取自 SDE）。",
        "",
        "## 逐条核对",
        "",
        "| 原字典写法 | 字典声称的英文名 | SDE 中文名 | SDE 分类 |",
        "|---|---|---|---|",
    ]
    for a, e, zh, g in rows:
        out.append(f"| {a} | {e} | {zh} | {g} |")

    out += [
        "",
        "## 仍然可用的部分",
        "",
        "通用缩写与机制术语是对的，可以继续使用：",
        "",
        "T1 / T2 / T3、HAC、BC、ABC、BS、DPS / DPH、ECM / ECCM、",
        "AB（加力）、MWD（微曲）、安等、高安 / 低安 / 00、强爆、",
        "拦截泡泡、跃迁扰断（1 点）/ 跃迁扰频（2 点）、朝向、诱导。",
        "",
        "## 判据",
        "",
        "船名以 SDE 的 trnTranslations 中文表为准；社区昵称只在解释口语时引用，",
        "不进入正式对照表。",
    ]

    p = ROOT / "canonical" / "08_剧情与世界观" / "EVE缩写映射字典" / "rewrite.md"
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    for a, e, zh, g in rows:
        print(f"{a:<18} {e:<12} -> {zh:<12} {g}")


if __name__ == "__main__":
    main()

"""从剧情语料里抽取词条，生成可检索的世界观索引。

剧情文本 379 万字，占全库一半以上，但没有主角、没有目录、片段之间无顺序。
直接检索只能靠关键词碰运气。这里按势力 / 星域 / 组织 / 人物做一次归集：
每个词条列出出现次数与若干代表性原文，检索时能顺藤摸瓜。

不用模型，也不猜：只统计确定出现的专有名词，出现不到 3 次的不收录。
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LORE = ROOT / "canonical" / "08_剧情与世界观"

# 人工种子表：EVE 世界观里稳定存在的专有名词。
# 只用来定位，不预设内容——出现次数为 0 的会被自动剔除。
SEEDS = {
    "势力": ["艾玛帝国", "加达里经济合众国", "盖伦特联邦", "米玛塔尔共和国",
             "朱庇特帝国", "朱庇特", "三神裔", "冬眠者", "萨沙", "血袭者",
             "天使联合企业", "天蛇集团", "古斯塔斯", "莫德团", "姐妹会",
             "统合部", "EDENCOM", "新伊甸", "伊甸", "塔洛坎", "索罗",
             "印塔基", "天罚", "星际邦联", "萨鲁姆", "帝国卫队"],
    "星域": ["多迪克斯", "辛迪特", "天庭", "血脉", "德克廉", "黑渊", "特步特",
             "静寂谷", "维纳尔", "斐德", "普罗维登斯", "摩多", "米亚尔加",
             "卡多尔", "德里克", "迪特尼", "塞纳", "因塔", "科尔", "塔什蒙贡",
             "底特里德", "埃索特亚", "佩里根", "卡尼迪", "奥尼克斯", "库比肯",
             "格赫伦", "索罗文", "多梅尼", "阿提亚", "卡利巴尔", "雅兰",
             "图克尔", "杜雷尔", "德沃斯", "奥瑞尔", "帕拉丁",
             "源泉", "混浊", "大荒野", "险恶", "卡桑德拉", "辛迪加", "泛光",
             "沃尔斯", "库尔斯", "塔拉", "因卡", "阿诺", "奥贝", "尤拉",
             "赫克", "维洛勒", "阿姆", "朱庇特", "新伊甸", "伊甸", "虫洞空间"],
    "组织": ["海盗", "帝国海军", "联邦海军", "共和国舰队", "克隆人飞行员",
             "星际管理委员会", "真理部", "赤道", "深空拓殖", "伊甸联合阵线",
             "帝国卫队", "联邦情报局", "部落议会", "海军", "陆军",
             "联合阵线", "星际运输", "矿业公司", "黑市"],
    "人物": ["贾米尔", "塔里克", "多姆", "卡萨", "米莉", "德拉戈", "塞纳托尔",
             "提亚马特", "奥托", "阿利伊", "伊莎贝拉", "巴拉克",
             "萨鲁姆", "瓦勒里", "阿多尼斯", "马塔", "塞德里克", "尤兰达",
             "提多", "阿卡尔", "德雷克", "奥拉夫", "叶卡捷琳娜"],
}

FIELD = re.compile(r"[^\n。！？]{0,60}(%s)[^\n。！？]{0,60}[。！？]?")


def main() -> None:
    texts = []
    for p in LORE.rglob("source.md"):
        t = p.read_text(encoding="utf-8", errors="ignore")
        if len(t) > 500:
            texts.append((p.parent.name, t))
    total = sum(len(t) for _, t in texts)
    print(f"[lore] {len(texts)} 份来源，{total:,} 字")

    hits: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(
        lambda: {"docs": [], "snip": ""}))
    counts: dict[str, int] = defaultdict(int)

    for name, text in texts:
        flat = text.replace("\n", " ")
        for group, words in SEEDS.items():
            for w in words:
                n = text.count(w)
                if not n:
                    continue
                counts[w] += n
                rec = hits[group][w]
                if name not in rec["docs"]:
                    rec["docs"].append(name)
                if not rec["snip"]:
                    m = re.search(r"[^。！？]{0,60}" + re.escape(w) + r"[^。！？]{0,60}[。！？]",
                                  flat)
                    if m:
                        rec["snip"] = m.group(0).strip()[:150]

    kept = {g: {w: v for w, v in d.items() if counts[w] >= 3} for g, d in hits.items()}
    kept = {g: d for g, d in kept.items() if d}

    out = [
        "---",
        "id: canon-lore-index",
        "title: 世界观词条索引",
        "domain: 08_剧情与世界观",
        "subdomain: ",
        "type: canonical",
        "status: drafted",
        "sde_build: 3662168 / 2026-10-30",
        "verified: 2026-11-01",
        "---",
        "",
        "# 世界观词条索引",
        "",
        f"剧情语料 {total:,} 字，按势力 / 星域 / 组织 / 人物归集。",
        "每个词条给出全库出现次数、出现于哪些文档、以及一条代表性原文。",
        "低于 3 次的不收录——偶然提到一次的词不算世界观要素。",
        "",
    ]
    for group in ["势力", "星域", "组织", "人物"]:
        d = kept.get(group)
        if not d:
            continue
        out += [f"## {group}", ""]
        for w, info in sorted(d.items(), key=lambda x: -counts[x[0]]):
            out.append(f"### {w}")
            out.append(f"- 全库出现 **{counts[w]}** 次")
            if info["docs"]:
                out.append(f"- 主要出现在：{'、'.join(info['docs'][:3])}")
            if info["snip"]:
                out.append(f"- 原文：「{info['snip']}」")
            out.append("")

    d = LORE / "_topic_世界观词条索引"
    d.mkdir(parents=True, exist_ok=True)
    (d / "source.md").write_text("（本条目由剧情语料统计生成）\n", encoding="utf-8")
    (d / "meta.yaml").write_text(
        "\n".join(["title: 世界观词条索引", "domain: 08_剧情与世界观",
                   "subdomain: ", "origin: 08_剧情与世界观 全量统计",
                   f"chars: {sum(len(t) for _, t in texts)}", "status: drafted"]) + "\n",
        encoding="utf-8")
    body = "\n".join(out).rstrip() + "\n"
    (d / "rewrite.md").write_text(body, encoding="utf-8")

    n = sum(len(v) for v in kept.values())
    print(f"[lore] 收录词条 {n} 个，索引 {len(body):,} 字")
    for g, v in kept.items():
        print(f"  {g}: {len(v)} 个")


if __name__ == "__main__":
    main()

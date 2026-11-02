"""把剧情词条从「索引」升级成「条目」。

之前只做了索引（出现次数 + 一句原文），问「萨沙共和国的历史」只能捞到零散段落。
这里给每个词条建一个独立文档：定义 + 出现统计 + 3~5 段代表性原文。

原文一律照抄，不做摘要——剧情不是数值，摘要会引入模型的理解偏差。
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LORE = ROOT / "canonical" / "08_剧情与世界观"
OUT = LORE / "词条"


def load_entities() -> dict[str, dict]:
    """从词条索引里读出全部词条及其分类。"""
    p = LORE / "_topic_世界观词条索引" / "rewrite.md"
    if not p.exists():
        return {}
    text = p.read_text(encoding="utf-8")
    out, group = {}, ""
    for line in text.splitlines():
        if line.startswith("## "):
            group = line[3:].strip()
        elif line.startswith("### "):
            out[line[4:].strip()] = {"group": group}
    return out


def paragraphs() -> list[tuple[str, str]]:
    """(文档名, 段落) 列表，来自剧情语料原文。"""
    out = []
    for p in LORE.rglob("source.md"):
        if "词条" in str(p.parent):
            continue
        name = p.parent.name
        text = p.read_text(encoding="utf-8", errors="ignore")
        for para in re.split(r"\n\s*\n", text):
            para = para.strip()
            if 80 <= len(para) <= 900:
                out.append((name, para))
    return out


def quality(p: str) -> float:
    """段落可用度：中文字符占比高、且不含 OCR 噪声。

    有些原文是 PDF 转的，满篇「9 H3 F5 _) s:」这类残留，
    直接摘出来当词条内容会很难看，也会污染检索。
    """
    if len(p) < 80:
        return 0.0
    cjk = sum(1 for ch in p if "\u4e00" <= ch <= "\u9fff")
    ratio = cjk / len(p)
    # 单字母/数字与中文交替出现，是 OCR 断行的典型特征
    noisy = len(re.findall(r"[A-Za-z0-9]\s+[A-Za-z0-9]\s+[A-Za-z0-9]", p))
    junk = sum(1 for ch in p if ch in "\$\\\|@#^")
    return ratio - 0.02 * noisy - 0.05 * junk


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-len", type=int, default=100)
    ap.add_argument("--max-quote", type=int, default=5)
    ap.add_argument("--min-quality", type=float, default=0.55)
    args = ap.parse_args()

    ents = load_entities()
    if not ents:
        print("没有词条索引，先跑 build_lore_index.py")
        return
    raw = paragraphs()
    paras = [(d, p) for d, p in raw if quality(p) >= args.min_quality]
    print(f"[lore] 词条 {len(ents)} 个，候选段落 {len(raw):,} → 过滤后 {len(paras):,} 段")

    OUT.mkdir(parents=True, exist_ok=True)
    made = 0
    for name, meta in ents.items():
        hits = [(doc, p) for doc, p in paras if name in p]
        if len(hits) < 2:
            continue
        # 按段落质量排序：剧情语料的正文段落优先于攻略里的噪声段
        hits.sort(key=lambda dp: -quality(dp[1]))
        # 同一文档最多取两段，保证覆盖面
        per_doc = defaultdict(int)
        picked = []
        for doc, p in hits:
            if per_doc[doc] >= 2:
                continue
            per_doc[doc] += 1
            picked.append((doc, p))
            if len(picked) >= args.max_quote:
                break
        if not picked:
            continue

        d = OUT / name.replace("/", "_")
        d.mkdir(parents=True, exist_ok=True)
        body = [f"# {name}", "",
                f"分类：{meta['group']}　　全库提及 {len(hits)} 段，本节收录 {len(picked)} 段。",
                "", "以下均为原文摘录，未作改写。", ""]
        for i, (doc, p) in enumerate(picked, 1):
            body += [f"## 摘录 {i}（出自《{doc}》）", "", p, ""]
        text = "\n".join(body).rstrip() + "\n"

        (d / "source.md").write_text(
            "（本条目由剧情语料摘录汇编，原文见各摘录出处）\n", encoding="utf-8")
        (d / "meta.yaml").write_text(
            "\n".join([f"title: {name}", "domain: 08_剧情与世界观",
                       "subdomain: 词条", "type: canonical", "status: drafted",
                       f"mentions: {len(hits)}"]) + "\n", encoding="utf-8")
        (d / "rewrite.md").write_text(text, encoding="utf-8")
        made += 1

    print(f"[lore] 生成条目 {made} 个 -> {OUT}")


if __name__ == "__main__":
    main()

"""把全部文档整理成分类文件夹，并统一 YAML 头。

规范来自人工清洗的 05_生产与经济.7z：文件夹名 = domain/subdomain，
文件头 = id / title / domain / subdomain / source / eve_sde / verified /
accuracy / freshness / version_note。

我们没有人工审计的人力，但结构必须一致——这样人工审计过的文件可以直接放进来，
不会被覆盖，也不会因为格式不同而丢元数据。

缺少头的文档会被自动补全，并标 accuracy: 未核验，与人工文件区分开。

用法：
  python tools/organize.py --out corpus
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from curate import clean  # noqa: E402

# 一级分类（沿用人工库的编号习惯）
DOMAINS = {
    "新手": "01_新手与入门",
    "装配": "02_舰船与装配",
    "战斗": "03_战斗与PVP",
    "任务": "04_任务与刷怪",
    "生产": "05_生产与经济",
    "机制": "06_机制与公式",
    "市场": "07_市场与贸易",
    "剧情": "08_剧情与世界观",
    "百科": "09_百科与资料",
    "工具": "10_工具与站点",
    "组织": "11_军团与组织",
    "其他": "99_杂项",
}

# 生产类下面的子类
SUBDOMAINS = [
    ("深渊", "05.6_深渊"),
    ("挖坟", "05.5_探索与挖坟"),
    ("考古", "05.5_探索与挖坟"),
    ("扫描", "05.5_探索与挖坟"),
    ("挖矿", "05.2_挖矿"),
    ("行星", "05.3_行星开发"),
    ("远征", "05.4_远征与异常"),
    ("卫队", "03.2_势力战争"),
    ("任务", "04.1_任务攻略"),
    ("刷怪", "05.1_刷怪与收益"),
    ("市场", "07.1_市场与贸易"),
    ("贸易", "07.1_市场与贸易"),
    ("装配", "02.1_装配方案"),
    ("配船", "02.1_装配方案"),
]

FM = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)


def parse_fm(text: str) -> tuple[dict, str]:
    m = FM.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta, text[m.end():]


def dump_fm(meta: dict) -> str:
    order = ["id", "title", "domain", "subdomain", "source", "origin_category",
             "eve_sde", "verified", "accuracy", "freshness", "version_note"]
    keys = [k for k in order if k in meta] + [k for k in meta if k not in order]
    body = "\n".join(f"{k}: {meta[k]}" for k in keys)
    return f"---\n{body}\n---\n\n"


def pick_domain(category: str, name: str, meta: dict) -> tuple[str, str]:
    """返回 (domain_dir, subdomain_dir)。人工给的 subdomain 优先。"""
    if meta.get("subdomain"):
        sub = meta["subdomain"]
        dom = meta.get("domain") or DOMAINS.get(category, "99_杂项")
        return dom, sub
    for kw, sub in SUBDOMAINS:
        if kw in name:
            dom = DOMAINS.get(category, "99_杂项")
            # 卫队/任务这类关键词可能跨类，跟随关键词
            if sub.startswith("05") and dom != "05_生产与经济":
                dom = "05_生产与经济"
            if sub.startswith("03") or sub.startswith("04"):
                dom = "03_战斗与PVP" if sub.startswith("03") else "04_任务与刷怪"
            if sub.startswith("07") or sub.startswith("02"):
                dom = "07_市场与贸易" if sub.startswith("07") else "02_舰船与装配"
            return dom, sub
    dom = DOMAINS.get(category, "99_杂项")
    return dom, ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "corpus"))
    ap.add_argument("--curated", default=str(ROOT / "data" / "curated"))
    ap.add_argument("--report", default=str(ROOT / "data" / "curated.jsonl"))
    ap.add_argument("--incoming", default=str(ROOT / "data" / "incoming"))
    ap.add_argument("--sde", default="3662168 / 2026-10-30")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    out = Path(args.out)
    if out.exists() and args.force:
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    rows = [json.loads(l) for l in Path(args.report).read_text(encoding="utf-8").splitlines()
            if l.strip()]
    ok = [r for r in rows if r.get("status") == "ok"]
    print(f"[organize] 待整理 {len(ok)} 篇")

    manifest = []
    cands: dict[tuple, dict] = {}
    RANK = {"已核验": 5, "AI已核验": 4, "已阅览": 3, "未核验": 1}

    reviews: dict[str, dict] = {}
    rpath = ROOT / "data" / "reviews.jsonl"
    if rpath.exists():
        for line in rpath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                r = json.loads(line)
                reviews[r["title"]] = r
        print(f"[organize] 已载入人工判定 {len(reviews)} 条")

    def add(meta: dict, text: str, src: str) -> None:
        dom, sub = pick_domain(meta.get("_cat", "其他"), meta.get("title", ""), meta)
        # 必须写回头部：否则下游（scaffold / 索引）只看正文头，拿不到分类，
        # 分类就只存在于路径里，一搬目录就丢了。
        meta["domain"] = dom
        meta["subdomain"] = sub
        d = out / dom / sub if sub else out / dom
        title = re.sub(r'[\\/:*?"<>|]', "_", meta.get("title") or "untitled")[:100]
        # 人工判定层：把 AI/人工的复核结论注入文件头，避免同一处反复被误判
        rv = reviews.get(re.sub(r"_\d+$", "", title))
        if rv:
            meta["ai_verdict"] = rv.get("verdict", "")
            meta["ai_review"] = rv.get("note", "")
            meta["ai_review_date"] = rv.get("date", "")
            if rv.get("verdict") == "ok" and meta.get("accuracy") == "未核验":
                meta["accuracy"] = "AI已核验"
        # 去重键去掉尾部 _1/_2：自动库与人工库的同一篇常常一个带后缀一个不带
        key = (str(d), re.sub(r"_\d+$", "", title))
        cand = {"dir": d, "title": title, "meta": meta, "text": text, "src": src,
                "rank": RANK.get(meta.get("accuracy", ""), 0), "chars": len(text)}
        # 同名文档只留一份：人工审计过的优先，其次留正文更长的。
        # 人工库和自动库大量重名，不选就会两版并存，检索时互相打架。
        old = cands.get(key)
        if old is None or (cand["rank"], cand["chars"]) > (old["rank"], old["chars"]):
            cands[key] = cand

    def flush() -> None:
        used: set[Path] = set()
        for cand in cands.values():
            d, title = cand["dir"], cand["title"]
            d.mkdir(parents=True, exist_ok=True)
            fp = d / f"{title}.md"
            i = 1
            while fp in used:
                fp = d / f"{title}_{i}.md"
                i += 1
            used.add(fp)
            fp.write_text(dump_fm(cand["meta"]) + cand["text"], encoding="utf-8")
            m = cand["meta"]
            rel = fp.relative_to(out).parts
            manifest.append({"path": str(fp.relative_to(out)), "domain": rel[0],
                             "subdomain": rel[1] if len(rel) > 2 else "",
                             "title": title, "chars": cand["chars"],
                             "accuracy": m.get("accuracy"),
                             "freshness": m.get("freshness"), "src": cand["src"]})

    # 1) 已清洗的 674 篇：头从原始文件取，正文用清洗后的
    for r in ok:
        src = Path(r["src"])
        cur = Path(args.curated) / r["out"]
        if not cur.exists():
            continue
        text = cur.read_text(encoding="utf-8")
        meta, _ = parse_fm(src.read_text(encoding="utf-8", errors="ignore")) if src.exists() else ({}, "")
        meta.setdefault("id", hashlib.md5(str(src).encode()).hexdigest()[:12])
        meta.setdefault("title", Path(r["out"]).stem)
        meta.setdefault("source", "ima知识库" if "ima" in str(src) else "转换文档")
        meta.setdefault("eve_sde", args.sde)
        meta.setdefault("accuracy", "未核验")
        meta.setdefault("freshness", "未知")
        meta.setdefault("version_note", "自动分类，未人工审计")
        meta["_cat"] = r.get("category", "其他")
        add(meta, text, str(src))

    # 2) 人工清洗的收件箱：保留其 domain/subdomain 与审计状态
    inc = Path(args.incoming)
    if inc.exists():
        n_in = 0
        for fp in sorted(inc.rglob("*.md")):
            raw = fp.read_text(encoding="utf-8", errors="ignore")
            meta, body = parse_fm(raw)
            # 人工库也要过一遍清洗：它的正文同样来自 PDF/Word 转换，
            # 一样有断词和页眉。跳过清洗会让"已审计"的文件反而更脏。
            text, _ = clean(body)
            meta.setdefault("id", hashlib.md5(str(fp).encode()).hexdigest()[:12])
            meta.setdefault("title", fp.stem.replace("（已审计）", "").replace("（已阅览）", ""))
            meta.setdefault("source", "人工清洗库")
            meta.setdefault("accuracy", "已核验" if "已审计" in fp.name else "已阅览")
            meta.setdefault("eve_sde", args.sde)
            meta["_cat"] = "生产"
            add(meta, text, str(fp))
            n_in += 1
        print(f"[organize] 并入人工清洗 {n_in} 篇")

    flush()

    (out / "_manifest.jsonl").write_text(
        "\n".join(json.dumps(m, ensure_ascii=False) for m in manifest) + "\n",
        encoding="utf-8")

    # 每个文件夹一份索引，读之前先看目录
    dirs: dict[Path, list[dict]] = {}
    for m in manifest:
        p = out / m["path"]
        dirs.setdefault(p.parent, []).append(m)
    for d, items in dirs.items():
        items.sort(key=lambda x: x["title"] or "")
        lines = [f"# {d.relative_to(out)}", "", f"共 {len(items)} 篇", ""]
        for it in items:
            flag = "已审计" if it["accuracy"] == "已核验" else ""
            lines.append(f"- [{it['title']}]({Path(it['path']).name})  "
                         f"{it['chars']:,} 字 {flag}")
        (d / "_index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[organize] 完成 {len(manifest)} 篇 -> {out}")
    from collections import Counter
    c = Counter(m["domain"] for m in manifest)
    for k, v in sorted(c.items()):
        print(f"    {k:<22} {v:>4} 篇")


if __name__ == "__main__":
    main()

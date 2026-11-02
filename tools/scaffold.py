"""为每一篇文档建立独立文件夹：source.md + meta.yaml + rewrite.md。

结构：
  canonical/<域>/<子域>/<标题>/
      source.md    原文（不含 YAML 头）
      meta.yaml    分类与来源
      rewrite.md   重写稿（初始为占位，由 AI 逐篇填写）

为什么一篇一个文件夹：
  重写不是"整体替换"，而是"原文与重写稿并存、可逐篇比对"。
  合并成一个大文件后，就没法知道哪句话来自哪篇、改过没有。

用法：
  python tools/scaffold.py
  python tools/scaffold.py --only 05.6_深渊
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FM = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
BAD = re.compile(r'[\\/:*?"<>|]')


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


def safe(s: str, limit: int = 80) -> str:
    return BAD.sub("_", s).strip()[:limit]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(ROOT / "corpus"))
    ap.add_argument("--out", default=str(ROOT / "canonical"))
    ap.add_argument("--only", default=None, help="只处理某个子域，如 05.6_深渊")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    corpus = Path(args.corpus)
    out = Path(args.out)
    if out.exists() and args.force:
        # 保留已有的重写稿：先备份 rewrite.md 内容
        backup = {}
        for p in out.rglob("rewrite.md"):
            backup[str(p.parent.relative_to(out))] = p.read_text(encoding="utf-8")
        shutil.rmtree(out)
        out.mkdir(parents=True)
    else:
        backup = {}
        out.mkdir(parents=True, exist_ok=True)

    docs = []
    for fp in sorted(corpus.rglob("*.md")):
        if fp.name == "_index.md":
            continue
        meta, body = parse_fm(fp.read_text(encoding="utf-8", errors="ignore"))
        if not meta.get("domain"):
            continue
        if args.only and args.only not in str(fp):
            continue
        docs.append((fp, meta, body))

    print(f"[scaffold] 待建 {len(docs)} 篇")

    progress = []
    seen: set[Path] = set()
    for fp, meta, body in docs:
        domain = meta.get("domain", "99_待分类")
        sub = meta.get("subdomain", "")
        title = safe(meta.get("title") or fp.stem)
        d = out / domain / sub / title if sub else out / domain / title
        i = 1
        while d in seen:
            d = d.with_name(f"{title}_{i}")
            i += 1
        seen.add(d)
        d.mkdir(parents=True, exist_ok=True)

        (d / "source.md").write_text(body.strip(), encoding="utf-8")

        m = {
            "title": meta.get("title") or fp.stem,
            "domain": domain,
            "subdomain": sub,
            "origin": str(fp.relative_to(ROOT)),
            "accuracy": meta.get("accuracy", "未核验"),
            "ai_verdict": meta.get("ai_verdict", ""),
            "year": meta.get("year", ""),
            "chars": len(body.strip()),
            "status": "pending",
        }
        (d / "meta.yaml").write_text(
            "\n".join(f"{k}: {v}" for k, v in m.items()) + "\n", encoding="utf-8")

        key = str(d.relative_to(out))
        if key in backup:
            (d / "rewrite.md").write_text(backup[key], encoding="utf-8")
            m["status"] = "drafted"
        elif not (d / "rewrite.md").exists():
            (d / "rewrite.md").write_text(
                f"# {m['title']}\n\n> 状态：待重写\n"
                f"> 原文：source.md（{m['chars']:,} 字）\n"
                f"> 分类：{domain}" + (f" / {sub}" if sub else "") + "\n"
                f"> 规范：见 canonical/_README.md\n", encoding="utf-8")

        progress.append(m)

    (out / "_progress.json").write_text(
        json.dumps(progress, ensure_ascii=False, indent=1), encoding="utf-8")

    from collections import Counter
    c = Counter(p["domain"] for p in progress)
    print(f"[scaffold] 建好 {len(progress)} 个文件夹")
    for k, v in sorted(c.items()):
        print(f"    {k:<22} {v:>4}")


if __name__ == "__main__":
    main()

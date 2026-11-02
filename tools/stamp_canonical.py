"""给 canonical 下的 rewrite.md 补 YAML 头，使其被索引识别为「权威」层级。

重写稿是结论，不是素材：
  * 必须带 type: canonical，索引才会给权威权重
  * source.md 不进索引（原文已在 corpus/ 里），否则同一内容会被检索两次
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FM = re.compile(r"\A---\s*\n", re.S)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT / "canonical"))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    root = Path(args.root)
    n = 0
    for meta_p in sorted(root.rglob("meta.yaml")):
        d = meta_p.parent
        rw = d / "rewrite.md"
        if not rw.exists():
            continue
        meta = {}
        for line in meta_p.read_text(encoding="utf-8").splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip()
        body = rw.read_text(encoding="utf-8")
        if FM.match(body) and not args.force:
            continue
        body = FM.sub("", body, count=1) if FM.match(body) else body
        # 若已有旧头，先剥掉到第二个 ---
        if body.startswith("title:") or body.startswith("id:"):
            parts = body.split("\n---\n", 1)
            if len(parts) == 2:
                body = parts[1].lstrip("\n")
        drafted = meta.get("status") == "drafted"
        head = [
            "---",
            f"id: canon-{abs(hash(str(d))) % 10**10:010d}",
            f"title: {meta.get('title', d.name)}",
            f"domain: {meta.get('domain', '')}",
            f"subdomain: {meta.get('subdomain', '')}",
            # 未重写的占位稿不能标成 canonical，否则空文档会以权威权重进索引
            f"type: {'canonical' if drafted else 'placeholder'}",
            f"status: {'drafted' if drafted else 'pending'}",
            "sde_build: 3662168 / 2026-10-30",
            "verified: 2026-11-01",
            f"origin: {meta.get('origin', '')}",
            "---",
            "",
        ]
        rw.write_text("\n".join(head) + body.lstrip("\n"), encoding="utf-8")
        n += 1

    print(f"[stamp] 已补头 {n} 篇")


if __name__ == "__main__":
    main()

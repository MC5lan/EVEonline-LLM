"""重跑那些压缩过度、丢信息严重的重写稿。

判据：源文 > 8000 字，但重写稿 < 800 字（压缩比 < 10%）。这类多半是没有小节
标题的长文，旧的分节摘要把它们压成了一句开头。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from rewrite_bulk import structure_long  # noqa: E402

MIN_SRC = 8000
MAX_REWRITE = 800


def main() -> None:
    root = ROOT / "canonical"
    n = 0
    for mp in sorted(root.rglob("meta.yaml")):
        d = mp.parent
        src, rw = d / "source.md", d / "rewrite.md"
        if not src.exists() or not rw.exists():
            continue
        body = src.read_text(encoding="utf-8", errors="ignore")
        cur = rw.read_text(encoding="utf-8")
        cur_body = cur.split("---", 2)[-1] if cur.startswith("---") else cur
        if len(body) < MIN_SRC or len(cur_body.strip()) >= MAX_REWRITE:
            continue

        meta = {}
        for line in mp.read_text(encoding="utf-8").splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip()

        text = structure_long(meta.get("title", d.name), body)
        head = cur.split("---", 2)[0] + "---\n\n" if cur.startswith("---") else ""
        rw.write_text(head + text.lstrip("\n"), encoding="utf-8")
        n += 1
        print(f"  {len(cur_body.strip()):>5} -> {len(text):>5}  {d.relative_to(root)}")

    print(f"[refill] 重写 {n} 篇")


if __name__ == "__main__":
    main()

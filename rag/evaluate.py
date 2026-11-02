"""检索质量评测。

在调模型之前先把检索调对。检索错了，再强的模型也只能编。

评测集格式（每行）：
  {"q": "问题", "must": ["必须出现在检索结果里的词", "..."]}

指标：
  term recall   must 里的词平均命中率（跨全部 top-k 块）
  all-hit rate  所有 must 词都被命中的题目占比
  MRR           第一个含 must 词的块的名次倒数的平均

阈值参考：
  all-hit < 70%  → 调 chunk 大小/重叠，或换 embedding 模型
  all-hit > 90%  → 检索够用了，可以接生成模型

用法：
  python -m rag.evaluate --eval rag/eval_set.example.jsonl
  python -m rag.evaluate --eval my_eval.jsonl --k 8 --alpha 0.45
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rag.retriever import Retriever


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="index")
    ap.add_argument("--eval", default="rag/eval_set.example.jsonl")
    ap.add_argument("--k", type=int, default=6)
    ap.add_argument("--alpha", type=float, default=0.55)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    rows = [json.loads(l) for l in Path(args.eval).read_text(encoding="utf-8").splitlines()
            if l.strip()]
    r = Retriever(args.index, alpha=args.alpha)
    print(f"[eval] {len(rows)} 题 / 索引 {r.meta['n_chunks']} 块 / α={args.alpha} / k={args.k}\n")

    term_hits, all_hit, rr = 0, 0, 0.0

    for row in rows:
        q, must = row["q"], row.get("must", [])
        hits = r.search(q, k=args.k)
        ctx = " ".join(h["text"].lower() for h in hits)

        found = [m for m in must if m.lower() in ctx]
        term_hits += len(found) / max(1, len(must))
        all_ok = len(found) == len(must)
        all_hit += int(all_ok)

        rank = None
        for i, h in enumerate(hits, 1):
            if any(m.lower() in h["text"].lower() for m in must):
                rank = i
                break
        rr += 0.0 if rank is None else 1.0 / rank

        if args.verbose or not all_ok:
            mark = "✓" if all_ok else "✗"
            miss = [m for m in must if m not in found]
            print(f"{mark} {q[:46]}")
            if miss:
                print(f"    缺: {miss}")

    n = len(rows)
    print(f"\nterm recall  {term_hits/n:.1%}")
    print(f"all-hit      {all_hit/n:.1%}")
    print(f"MRR          {rr/n:.3f}")

    if all_hit / n < 0.70:
        print("\n检索不达标。优先检查：")
        print("  1. 块太大/太小 —— 试 --target 300 或 800 重建索引")
        print("  2. α 偏高 —— EVE 专有名词多，试 --alpha 0.4")
        print("  3. embedding 模型对英文缩写不敏感 —— 这正是 BM25 存在的理由，先调 α")
    else:
        print("\n检索可用，可以接生成模型。")


if __name__ == "__main__":
    main()

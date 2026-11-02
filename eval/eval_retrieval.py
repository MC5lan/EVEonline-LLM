"""检索质量评测：recall@k / MRR。

为什么单独测检索：
  端到端问答分数掩盖了检索的真实水平——答错可能是模型不会组织，
  也可能是根本没召回对的资料。两个问题修法完全不同。

怎么造题：
  从每篇文档正文里截一段（去掉标题词），当作「用户会怎么问」，
  标准答案是这篇文档本身。这样查询和标题不重合，才有区分度。
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def docs() -> list[tuple[str, str, str]]:
    """(来源名, 标题, 正文)"""
    out = []
    for p in (ROOT / "canonical").rglob("rewrite.md"):
        text = p.read_text(encoding="utf-8", errors="ignore")
        body = text.split("---", 2)[-1] if text.startswith("---") else text
        body = body.strip()
        if len(body) < 400:          # 太短的文档没有可用正文
            continue
        out.append((p.parent.name, p.parent.name, body))
    return out


def make_query(title: str, body: str, rng: random.Random) -> str:
    """从正文取一段做查询，并去掉标题里的词，避免白送。"""
    paras = [x.strip() for x in re.split(r"\n\s*\n", body) if 60 <= len(x.strip()) <= 400]
    if not paras:
        return ""
    s = rng.choice(paras)
    s = re.sub(r"[#*>`\-]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    for w in re.findall(r"[\u4e00-\u9fff]{2,}", title):
        s = s.replace(w, " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s[:120]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--rerank", action="store_true", help="用交叉编码器重排")
    ap.add_argument("--pool", type=int, default=30, help="重排前的候选数")
    args = ap.parse_args()

    from rag.retriever import Retriever

    rng = random.Random(args.seed)
    all_docs = docs()
    rng.shuffle(all_docs)

    cases = []
    for name, title, body in all_docs:
        q = make_query(title, body, rng)
        if len(q) < 20:
            continue
        cases.append({"query": q, "gold": name})
        if len(cases) >= args.n:
            break

    print(f"[ret] 题数 {len(cases)}，开始检索…")
    r = Retriever()
    rr = None
    if args.rerank:
        from rag.rerank import Reranker
        rr = Reranker()
        print(f"[ret] 重排模型 {rr.name}，候选池 {args.pool}")

    hit_at = defaultdict(int)
    mrr = 0.0
    misses = []
    for i, c in enumerate(cases, 1):
        if rr is not None:
            hits = rr.rerank(c["query"], r.search(c["query"], k=args.pool), topk=args.k)
        else:
            hits = r.search(c["query"], k=args.k)
        srcs = [h.get("source") for h in hits]
        rank = None
        for j, s in enumerate(srcs, 1):
            if s == c["gold"]:
                rank = j
                break
        if rank:
            mrr += 1.0 / rank
            for k in (1, 3, 5, 10):
                if rank <= k:
                    hit_at[k] += 1
        elif len(misses) < 5:
            misses.append((c["query"][:50], c["gold"], srcs[:3]))
        if i % 100 == 0:
            print(f"  {i}/{len(cases)}", flush=True)

    n = len(cases)
    print("\n" + "=" * 46)
    print(f"{'指标':<12}{'数值':>10}")
    print("-" * 46)
    for k in (1, 3, 5, 10):
        print(f"recall@{k:<4}{hit_at[k]/n*100:>9.1f}%")
    print(f"MRR        {mrr/n:>10.3f}")
    print("=" * 46)

    print("\n未召回样例：")
    for q, gold, top in misses:
        print(f"  查询：{q}")
        print(f"  期望：{gold}")
        print(f"  实际：{top}")
        print()


if __name__ == "__main__":
    main()

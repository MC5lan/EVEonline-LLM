"""下载通用中文语料，用来补足预训练所需的 token 量。

你的 EVE 语料只有约 250 万 tokens，而 77M 模型需要 5 亿 tokens。
缺的 99% 必须是通用中文，否则模型连通顺的句子都写不出来。

⚠️ 网络说明（本机实测）：
    huggingface.co  不可达
    hf-mirror.com   可达   ← 默认走这个镜像
    modelscope.cn   可达   ← 备选
脚本默认在导入 datasets 之前设置 HF_ENDPOINT=https://hf-mirror.com。

用法：
  python scripts/fetch_general.py --out data/general.txt --target-chars 700000000
  python scripts/fetch_general.py --out data/general.txt --source modelscope
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

MIRROR = "https://hf-mirror.com"

# (来源类型, 仓库, 子集)
HF_CANDIDATES = [
    ("uonlp/CulturaX", "zh"),
    ("uonlp/CulturaX", "zh-Hant"),
    ("wikimedia/wikipedia", "20231101.zh"),
]

MS_CANDIDATES = [
    ("modelscope/culturax", "zh"),
    ("AI-ModelScope/wikipedia-cn-20230720-filtered", None),
]


def write_stream(rows, out_path: Path, target_chars: int, text_keys=("text", "content")) -> int:
    from tqdm import tqdm

    written = 0
    with open(out_path, "w", encoding="utf-8") as f, \
         tqdm(total=target_chars, unit="char", unit_scale=True, desc="下载") as bar:
        for row in rows:
            text = ""
            for k in text_keys:
                if isinstance(row, dict) and row.get(k):
                    text = row[k]
                    break
            if not text or len(text) < 200:
                continue
            f.write(text.strip())
            f.write("\n\n<|eos|>\n\n")
            written += len(text)
            bar.update(len(text))
            if written >= target_chars:
                break
    return written


def from_hf(repo: str, subset: str, out: Path, target: int) -> int:
    from datasets import load_dataset

    print(f"[fetch] HF {repo} / {subset}")
    ds = load_dataset(repo, subset, split="train", streaming=True)
    return write_stream(ds, out, target)


def from_modelscope(repo: str, subset: str, out: Path, target: int) -> int:
    from modelscope.msdatasets import MsDataset

    print(f"[fetch] ModelScope {repo}")
    if subset:
        ds = MsDataset.load(repo, subset_name=subset, split="train")
    else:
        ds = MsDataset.load(repo, split="train")
    return write_stream(ds, out, target)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--target-chars", type=int, default=700_000_000)
    ap.add_argument("--min-chars", type=int, default=250_000_000)
    ap.add_argument("--source", choices=["hf", "modelscope", "auto"], default="auto")
    ap.add_argument("--hf-endpoint", default=MIRROR)
    args = ap.parse_args()

    # 必须在 import datasets 之前设置
    os.environ.setdefault("HF_ENDPOINT", args.hf_endpoint)
    print(f"[fetch] HF_ENDPOINT={os.environ['HF_ENDPOINT']}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    order = []
    if args.source in ("hf", "auto"):
        order += [("hf", r, s) for r, s in HF_CANDIDATES]
    if args.source in ("modelscope", "auto"):
        order += [("ms", r, s) for r, s in MS_CANDIDATES]

    for kind, repo, subset in order:
        try:
            if kind == "hf":
                n = from_hf(repo, subset, out, args.target_chars)
            else:
                n = from_modelscope(repo, subset, out, args.target_chars)
            print(f"[fetch] 完成 {n:,} 字符 -> {out}")
            if n < args.min_chars:
                print(f"⚠️  只有 {n:,} 字符，低于建议的 {args.min_chars:,}")
                print("   中文流畅度会明显下降。建议换数据源，或把 total_tokens 调小。")
            return
        except Exception as e:
            print(f"[fetch] {repo}/{subset} 失败: {type(e).__name__}: {e}", file=sys.stderr)
            continue

    sys.exit(
        "所有数据源都失败了。可选方案：\n"
        "  1. pip install modelscope 后重试：python scripts/fetch_general.py ... --source modelscope\n"
        "  2. 下中文维基 dump（dumps.wikimedia.org 本机可达），解压后转成纯文本：\n"
        "     https://dumps.wikimedia.org/zhwiki/latest/zhwiki-latest-pages-articles.xml.bz2\n"
        "     用 wikiextractor 或自己写个正则抽出正文，存成 data/general.txt\n"
        "  3. 用自己手头的通用中文资料（新闻、小说、论文、百科）拼一份\n"
        "     —— 只要 2.5 亿字符以上，来源不重要，通顺的中文就行"
    )


if __name__ == "__main__":
    main()

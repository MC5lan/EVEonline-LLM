"""把 canonical 语料编码成训练用 token 流。

输出：
  data/train.bin   uint16 训练集
  data/val.bin     uint16 验证集（2%）

为什么要留验证集：5M token 级别的语料很容易过拟合，没有验证集就看不出
「loss 在降」到底是学会了还是背下来了。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parent.parent


def docs():
    """按固定顺序产出文本，保证可复现。"""
    d = ROOT / "canonical"
    out = []
    for p in sorted(d.rglob("*")):
        if p.name == "rewrite.md":
            out.append(p)          # 重写稿：干净、结构化的知识
    for p in sorted(d.rglob("*")):
        if p.name == "source.md":
            out.append(p)          # 原文：补充细节与语感
    for p in sorted((ROOT / "data").glob("*.jsonl")):
        out.append(p)
    return out


def read_any(p: Path) -> str:
    if p.suffix == ".jsonl":
        parts = []
        with p.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for k in ("text", "note", "title"):
                    v = o.get(k)
                    if isinstance(v, str) and v:
                        parts.append(v)
        return "\n".join(parts)
    return p.read_text(encoding="utf-8", errors="ignore")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tokenizer", default=str(ROOT / "tokenizer" / "tokenizer.json"))
    ap.add_argument("--out", default=str(ROOT / "data"))
    ap.add_argument("--val-ratio", type=float, default=0.02)
    args = ap.parse_args()

    tok = Tokenizer.from_file(args.tokenizer)
    eos = tok.token_to_id("<eos>")
    out_dir = Path(args.out)

    files = docs()
    print(f"[export] {len(files)} 个来源")

    ids: list[int] = []
    for i, p in enumerate(files, 1):
        t = read_any(p)
        if not t.strip():
            continue
        ids.extend(tok.encode(t).ids)
        ids.append(eos)                      # 文档之间用 eos 分隔
        if i % 300 == 0:
            print(f"  {i}/{len(files)}  累计 {len(ids):,} token")

    arr = np.array(ids, dtype=np.uint16)
    n_val = int(len(arr) * args.val_ratio)
    # 验证集从尾部切，避免和训练集重叠
    train, val = arr[:-n_val], arr[-n_val:]

    train.tofile(out_dir / "train.bin")
    val.tofile(out_dir / "val.bin")

    print(f"[export] 总 token {len(arr):,}")
    print(f"  训练 {len(train):,} -> data/train.bin")
    print(f"  验证 {len(val):,} -> data/val.bin")
    print(f"  词表 {tok.get_vocab_size():,}")


if __name__ == "__main__":
    main()

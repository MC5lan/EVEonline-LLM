"""训练 EVE 专用 BPE 分词器。

为什么自己训：
  现成中文词表（如 BERT 的 21k）是按通用语料切的，对本项目里大量
  舰船名、模块名、型号编号没有专门合并，一个「多米尼克斯级」会被切成
  五六个 token。自己训能把这类专名压成一两个 token，等于白赚上下文。

为什么 24k：
  语料 817 万字符，词表再大会出现大量只出现一两次的合并，浪费参数
  （词表在嵌入层占用 vocab × d_model 个参数，24k 已是 9.4M）。

用法：
  python tools/train_tokenizer.py
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from tokenizers import Tokenizer, models, pre_tokenizers, decoders, trainers
from tokenizers.processors import ByteLevel as ByteLevelProcessor

ROOT = Path(__file__).resolve().parent.parent

SPECIALS = [
    "<pad>", "<bos>", "<eos>", "<unk>",
    "<im_start>", "<im_end>",
    "<|user|>", "<|assistant|>", "<|system|>", "<|context|>",
]


def corpus_files():
    for p in (ROOT / "canonical").rglob("*.md"):
        if p.name in ("source.md", "rewrite.md"):
            yield p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vocab", type=int, default=24576)
    ap.add_argument("--out", default=str(ROOT / "tokenizer"))
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    files = list(corpus_files())
    print(f"[tok] 语料 {len(files)} 个文件")

    tok = Tokenizer(models.BPE(unk_token="<unk>"))
    tok.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    tok.decoder = decoders.ByteLevel()
    tok.post_processor = ByteLevelProcessor(trim_offsets=False)

    trainer = trainers.BpeTrainer(
        vocab_size=args.vocab,
        special_tokens=SPECIALS,
        initial_alphabet=pre_tokenizers.ByteLevel.alphabet(),
        show_progress=True,
        min_frequency=2,
    )

    def it():
        for p in files:
            yield p.read_text(encoding="utf-8", errors="ignore")

    tok.train_from_iterator(it(), trainer=trainer)
    tok.save(str(out / "tokenizer.json"))

    # 压缩率评估：字符数 / token 数
    total_chars = total_tokens = 0
    samples = []
    for i, p in enumerate(files):
        t = p.read_text(encoding="utf-8", errors="ignore")
        n = len(tok.encode(t).ids)
        total_chars += len(t)
        total_tokens += n
        if i < 5:
            samples.append((p.parent.name, len(t), n))

    ratio = total_chars / max(1, total_tokens)
    print(f"[tok] 字符 {total_chars:,} → token {total_tokens:,}")
    print(f"[tok] 压缩率 {ratio:.2f} 字/token  （越大越好）")

    # 专名检查
    for s in ["多米尼克斯级", "伊什塔级", "深渊纤维", "三神裔", "无畏级",
              "高能量槽", "跃迁扰频器", "吉斯特100MN加力燃烧器"]:
        ids = tok.encode(s).ids
        print(f"    {s:<18} {len(ids)} token  {ids}")
    return ratio


if __name__ == "__main__":
    main()

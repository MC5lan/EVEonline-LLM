"""训 tokenizer + 把纯文本编码成 uint16 二进制。

为什么词表要在「通用 + 领域」混合语料上训：
只在 300 万字符上训，词表会严重偏向 EVE 术语，普通中文被切碎，
预训练效率直接崩一半。

为什么特殊 token 必须进 BpeTrainer：
用 add_special_tokens 后加的话，llama.cpp 转换时容易丢。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from tokenizers import Tokenizer, decoders, models, pre_tokenizers, trainers
from tqdm import tqdm

SPECIAL_TOKENS = ["<|pad|>", "<|eos|>", "<|im_start|>", "<|im_end|>"]


def train(args: argparse.Namespace) -> None:
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    tok = Tokenizer(models.BPE())
    tok.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    tok.decoder = decoders.ByteLevel()

    trainer = trainers.BpeTrainer(
        vocab_size=args.vocab_size,
        special_tokens=SPECIAL_TOKENS,
        initial_alphabet=pre_tokenizers.ByteLevel.alphabet(),
        show_progress=True,
    )

    files = [str(p) for p in args.inputs]
    print(f"[tokenize] 训练 BPE，词表 {args.vocab_size}，语料 {files}")
    tok.train(files, trainer)
    tok.save(str(out))
    print(f"[tokenize] 已保存 -> {out}")
    print(f"[tokenize] 词表实际大小: {tok.get_vocab_size()}")


def encode(args: argparse.Namespace) -> None:
    tok = Tokenizer.from_file(args.tokenizer)
    eos_id = tok.token_to_id("<|eos|>")
    if eos_id is None:
        sys.exit("tokenizer 里没有 <|eos|>，请重新训练")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    buf: list[np.ndarray] = []
    buf_len = 0
    chunk_chars = args.chunk_chars

    def flush(f) -> None:
        nonlocal buf, buf_len
        if not buf:
            return
        arr = np.concatenate(buf).astype(np.uint16)
        f.write(arr.tobytes())
        buf, buf_len = [], 0

    print(f"[encode] {args.input} -> {out}")
    with open(args.input, "r", encoding="utf-8", errors="ignore") as fin, \
         open(out, "wb") as fout:
        doc: list[str] = []
        size = 0
        for line in tqdm(fin, unit="line", desc="encode"):
            if args.doc_sep and line.strip() == args.doc_sep:
                if doc:
                    ids = tok.encode("".join(doc)).ids + [eos_id]
                    buf.append(np.asarray(ids, dtype=np.uint16))
                    buf_len += len(ids)
                    total += len(ids)
                    doc, size = [], 0
                if buf_len >= chunk_chars * 4:
                    flush(fout)
                continue

            doc.append(line)
            size += len(line)
            if size >= chunk_chars:
                ids = tok.encode("".join(doc)).ids + [eos_id]
                buf.append(np.asarray(ids, dtype=np.uint16))
                buf_len += len(ids)
                total += len(ids)
                doc, size = [], 0
                if buf_len >= chunk_chars * 4:
                    flush(fout)

        if doc:
            ids = tok.encode("".join(doc)).ids + [eos_id]
            buf.append(np.asarray(ids, dtype=np.uint16))
            total += len(ids)
        flush(fout)

    meta = {"tokens": total, "bytes": total * 2, "source": str(args.input)}
    Path(str(out) + ".meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"[encode] 完成，{total:,} tokens -> {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description="EVE-LM tokenizer 工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_train = sub.add_parser("train", help="训练 BPE")
    p_train.add_argument("--inputs", nargs="+", required=True)
    p_train.add_argument("--out", required=True)
    p_train.add_argument("--vocab-size", type=int, default=32000)
    p_train.set_defaults(func=train)

    p_enc = sub.add_parser("encode", help="编码为 uint16 bin")
    p_enc.add_argument("--tokenizer", required=True)
    p_enc.add_argument("--input", required=True)
    p_enc.add_argument("--out", required=True)
    p_enc.add_argument("--chunk-chars", type=int, default=4000,
                       help="每次送入 encode 的字符数，越大越快但内存越高")
    p_enc.add_argument("--doc-sep", default=None,
                       help="文档分隔行，如 <|eos|>；遇到即断句")
    p_enc.set_defaults(func=encode)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

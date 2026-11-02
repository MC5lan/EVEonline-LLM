"""bge-small-zh-v1.5 的 ONNX 推理封装（不依赖 torch / transformers）。

为什么自己写 tokenizer：这台机器装 torch 会卡在大文件下载，
而 onnxruntime 只有十几 MB。BGE 用的是标准 BERT 中文分词
（CJK 逐字切分 + WordPiece），逻辑很短，自己实现可控。

关键细节：
  * 句向量取 [CLS]，然后 L2 归一化（BGE 官方用法，不是 mean pooling）
  * 查询要加指令前缀，短问句检索效果明显更好
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import numpy as np

CLS, SEP, PAD, UNK = 101, 102, 0, 100
QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："


def _is_cjk(ch: str) -> bool:
    o = ord(ch)
    return (0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF
            or 0xF900 <= o <= 0xFAFF)


def _is_punct(ch: str) -> bool:
    return unicodedata.category(ch).startswith("P")


class BertTokenizer:
    def __init__(self, vocab_path: Path, max_len: int = 512):
        self.vocab: dict[str, int] = {}
        for i, line in enumerate(vocab_path.read_text(encoding="utf-8").splitlines()):
            self.vocab[line.rstrip("\n")] = i
        self.max_len = max_len
        self.unk = self.vocab.get("[UNK]", UNK)

    def _basic(self, text: str) -> list[str]:
        text = text.lower()
        out: list[str] = []
        buf = ""
        for ch in text:
            if ch.isspace():
                if buf:
                    out.append(buf)
                    buf = ""
            elif _is_cjk(ch):
                if buf:
                    out.append(buf)
                    buf = ""
                out.append(ch)
            elif _is_punct(ch):
                if buf:
                    out.append(buf)
                    buf = ""
                out.append(ch)
            else:
                buf += ch
        if buf:
            out.append(buf)
        return out

    def _wordpiece(self, word: str) -> list[int]:
        if len(word) > 100:
            return [self.unk]
        ids, start = [], 0
        while start < len(word):
            end = len(word)
            cur = None
            while start < end:
                piece = word[start:end]
                if start > 0:
                    piece = "##" + piece
                if piece in self.vocab:
                    cur = self.vocab[piece]
                    break
                end -= 1
            if cur is None:
                return [self.unk]
            ids.append(cur)
            start = end
        return ids

    def encode(self, text: str) -> tuple[list[int], list[int]]:
        ids = [CLS]
        for w in self._basic(text):
            ids.extend(self._wordpiece(w))
            if len(ids) >= self.max_len - 1:
                break
        ids = ids[: self.max_len - 1] + [SEP]
        mask = [1] * len(ids)
        return ids, mask


class BgeEmbedder:
    dim = 512

    def __init__(self, model_dir: str | Path, max_len: int = 512, threads: int = 8):
        import onnxruntime as ort

        d = Path(model_dir)
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads
        opts.log_severity_level = 3
        self.sess = ort.InferenceSession(str(d / "model.onnx"), opts,
                                         providers=["CPUExecutionProvider"])
        self.tok = BertTokenizer(d / "vocab.txt", max_len=max_len)
        self.name = "bge-small-zh-v1.5"

    def _run(self, texts: list[str]) -> np.ndarray:
        batch = [self.tok.encode(t) for t in texts]
        n = len(batch)
        L = max(len(ids) for ids, _ in batch)
        ids = np.zeros((n, L), dtype=np.int64)
        mask = np.zeros((n, L), dtype=np.int64)
        for i, (a, m) in enumerate(batch):
            ids[i, : len(a)] = a
            mask[i, : len(m)] = m
        out = self.sess.run(None, {
            "input_ids": ids,
            "attention_mask": mask,
            "token_type_ids": np.zeros_like(ids),
        })[0]
        cls = out[:, 0, :].astype(np.float32)
        norm = np.linalg.norm(cls, axis=1, keepdims=True)
        return cls / np.maximum(norm, 1e-8)

    def encode_docs(self, texts: list[str], batch: int = 32) -> np.ndarray:
        outs = []
        for i in range(0, len(texts), batch):
            outs.append(self._run(texts[i:i + batch]))
        return np.vstack(outs) if outs else np.zeros((0, self.dim), dtype=np.float32)

    def encode_query(self, text: str) -> np.ndarray:
        return self._run([QUERY_PREFIX + text])[0]


if __name__ == "__main__":
    import sys
    m = BgeEmbedder(sys.argv[1] if len(sys.argv) > 1 else "models/bge-small-zh")
    pairs = [
        ("无畏刷怪怎么配装", "无畏级刷怪配置与注意事项"),
        ("无畏刷怪怎么配装", "朱庇特帝国与四大帝国的关系"),
        ("深渊有几个等级", "深渊纤维共分七级，宁静为入门"),
        ("深渊有几个等级", "米玛塔尔共和国的历史"),
    ]
    for q, d in pairs:
        s = float(m.encode_query(q) @ m.encode_docs([d])[0])
        print(f"{s:.3f}  {q}  ~  {d}")

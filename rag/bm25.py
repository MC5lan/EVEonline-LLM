"""BM25 倒排索引（只依赖 numpy）。

为什么 RAG 里必须有 BM25，不能只用向量：
EVE 的专有名词大量是英文缩写（T3C / MWD / HAC / ISK / EHP）。
中文向量模型对这类 token 的语义区分很弱，容易把 MWD 和 AB 当成近义词，
而它们恰恰是玩家最需要区分的两个东西。
混合检索（向量 + BM25）是这类专有名词密集领域的标准解法。

分词策略（针对中英混排）：
  * 英文/数字：按词切，保留 T3C、MWD、ISK 这类整体
  * 中文：切成 bigram，不依赖 jieba，避免未登录词问题
"""
from __future__ import annotations

import re
from collections import defaultdict

import numpy as np

_ASCII = re.compile(r"[a-z0-9]+(?:[-_.][a-z0-9]+)*")
_CJK = re.compile(r"[\u4e00-\u9fff]+")


def tokenize(text: str) -> list[str]:
    s = text.lower()
    toks = _ASCII.findall(s)
    for run in _CJK.findall(s):
        if len(run) == 1:
            toks.append(run)
        else:
            toks.extend(run[i : i + 2] for i in range(len(run) - 1))
    return toks


def ascii_terms(text: str) -> list[str]:
    """查询里的英文/数字硬词，用于精确命中加权。

    注意必须先 lower()：正则只匹配小写，直接对原文 findall 会把
    "MWD" 这类全大写缩写全部漏掉（这个 bug 会让硬词加权静默失效）。
    """
    return [t for t in _ASCII.findall(text.lower()) if len(t) >= 2]


class BM25:
    """倒排索引版 BM25，查询时用 numpy 累加，6000 文档量级下 <5ms。"""

    def __init__(self, tokenized_docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.n = len(tokenized_docs)

        doc_len = np.zeros(self.n, dtype=np.float32)
        df: dict[str, int] = defaultdict(int)
        # term -> (doc_ids, tfs)
        post: dict[str, list[list[int]]] = defaultdict(lambda: [[], []])

        for did, toks in enumerate(tokenized_docs):
            doc_len[did] = len(toks)
            tf: dict[str, int] = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1
            for t, c in tf.items():
                df[t] += 1
                post[t][0].append(did)
                post[t][1].append(c)

        self.avgdl = float(doc_len.mean()) if self.n else 1.0
        self.doc_len = doc_len

        self.index: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        self.idf: dict[str, float] = {}
        for t, (ids, tfs) in post.items():
            self.index[t] = (np.asarray(ids, dtype=np.int32),
                             np.asarray(tfs, dtype=np.float32))
            # Lucene 式 idf，恒正
            self.idf[t] = float(np.log(1.0 + (self.n - df[t] + 0.5) / (df[t] + 0.5)))

    def scores(self, query_tokens: list[str]) -> np.ndarray:
        s = np.zeros(self.n, dtype=np.float32)
        k1, b = self.k1, self.b
        for t in set(query_tokens):
            entry = self.index.get(t)
            if entry is None:
                continue
            ids, tfs = entry
            denom = tfs + k1 * (1 - b + b * self.doc_len[ids] / self.avgdl)
            s[ids] += self.idf[t] * (tfs * (k1 + 1.0)) / denom
        return s

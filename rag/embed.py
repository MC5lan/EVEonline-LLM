"""向量化后端抽象。

两个 provider：

  st     sentence-transformers + bge-small-zh，**生产用**，语义质量好
  hash   特征哈希，纯 numpy，**零依赖**，只用来验证链路和做离线测试

为什么要有 hash：
  1. 4GB 卡装 torch 很慢，但检索管道必须在装模型之前就能验证对不对；
  2. 它让这台没有 GPU、没有 torch 的机器也能跑完整的建索引 + 检索 + 评测；
  3. 出问题时可以用它做对照，区分"是向量模型的锅"还是"是管道逻辑的锅"。

hash 的质量显著低于 bge，不要拿它上线。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："
DEFAULT_ST_MODEL = "BAAI/bge-small-zh-v1.5"
HASH_DIM = 1024


def _tokens(text: str) -> list[str]:
    from rag.bm25 import tokenize
    return tokenize(text)


class HashEmbedder:
    """字符/词级特征哈希。确定性、无依赖，适合管道测试。"""

    name = "hash"

    def __init__(self, dim: int = HASH_DIM):
        self.dim = dim

    def encode(self, texts: list[str], is_query: bool = False) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            for tok in _tokens(t):
                h = int(hashlib.md5(tok.encode("utf-8")).hexdigest()[:8], 16)
                out[i, h % self.dim] += 1.0
            out[i] = np.sign(out[i]) * np.log1p(np.abs(out[i]))
            n = float(np.linalg.norm(out[i]))
            if n > 0:
                out[i] /= n
        return out


class STEmbedder:
    """sentence-transformers，懒加载（避免没有 torch 的机器一 import 就炸）。"""

    name = "st"

    def __init__(self, model_name: str = DEFAULT_ST_MODEL):
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts: list[str], is_query: bool = False) -> np.ndarray:
        model = self._load()
        if is_query:
            texts = [QUERY_INSTRUCTION + t for t in texts]
        vecs = model.encode(texts, batch_size=64, normalize_embeddings=True,
                            convert_to_numpy=True, show_progress_bar=len(texts) > 200)
        return np.asarray(vecs, dtype=np.float32)


class BgeOnnxEmbedder:
    """bge-small-zh-v1.5 的 ONNX 版本，不需要 torch。

    接口对齐 STEmbedder/ HashEmbedder：encode(texts, is_query)。
    查询加指令前缀，文档不加——这是 BGE 的官方用法。
    """

    def __init__(self, model_dir: str | None = None):
        from rag.onnx_embed import BgeEmbedder, QUERY_PREFIX, BgeEmbedder as _B

        base = Path(__file__).resolve().parent.parent / "models" / "bge-small-zh"
        self._m = _B(model_dir or base)
        self.dim = 512
        self.name = "bge-small-zh-v1.5"

    def encode(self, texts: list[str], is_query: bool = False) -> np.ndarray:
        if isinstance(texts, str):
            texts = [texts]
        if is_query:
            return self._m._run([self._prefix() + t for t in texts])
        return self._m.encode_docs(texts)

    @staticmethod
    def _prefix() -> str:
        from rag.onnx_embed import QUERY_PREFIX
        return QUERY_PREFIX


def get_embedder(provider: str, model_name: str = DEFAULT_ST_MODEL,
                 dim: int = HASH_DIM):
    if provider == "hash":
        return HashEmbedder(dim)
    if provider == "st":
        return STEmbedder(model_name)
    if provider in ("bge", "onnx"):
        # model_name 默认是 HF 仓库名，不是本地路径；只有确实存在才当目录用
        p = model_name if model_name and Path(model_name).exists() else None
        return BgeOnnxEmbedder(p)
    raise ValueError(f"未知 provider: {provider}（可选 bge / st / hash）")

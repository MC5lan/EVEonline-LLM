"""重排（rerank）：用交叉编码器给「问题-段落」配对打分。

和向量检索的区别：
  向量检索是双塔——问题和文档各自编码，再算余弦，快但粗；
  交叉编码器把两者拼在一起过一遍模型，能捕捉词序、否定、限定关系，准但慢。
  所以只对召回结果的前 N 条重排，不对全库跑。

模型：bge-reranker-base（int8 量化，266MB，CPU 上 20 条约 0.5 秒）
"""
from __future__ import annotations

import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = ROOT / "models" / "bge-reranker"


class Reranker:
    def __init__(self, model_dir: str | Path | None = None, max_len: int = 512,
                 threads: int = 8):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        d = Path(model_dir or DEFAULT_DIR)
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads
        opts.log_severity_level = 3
        self.sess = ort.InferenceSession(str(d / "model.onnx"), opts,
                                         providers=["CPUExecutionProvider"])
        self.tok = Tokenizer.from_file(str(d / "tokenizer.json"))
        self.tok.enable_truncation(max_length=max_len)
        self.max_len = max_len
        self.name = "bge-reranker-base"

    def score(self, query: str, docs: list[str]) -> np.ndarray:
        if not docs:
            return np.zeros(0, dtype=np.float32)
        encs = [self.tok.encode(query, d) for d in docs]
        n = len(encs)
        L = max(len(e.ids) for e in encs)
        ids = np.zeros((n, L), dtype=np.int64)
        mask = np.zeros((n, L), dtype=np.int64)
        for i, e in enumerate(encs):
            ids[i, : len(e.ids)] = e.ids
            mask[i, : len(e.ids)] = 1
        out = self.sess.run(None, {"input_ids": ids, "attention_mask": mask})[0]
        return out.reshape(-1).astype(np.float32)

    def rerank(self, query: str, hits: list[dict], topk: int | None = None) -> list[dict]:
        """对 hits 重排，返回带 rerank_score 的新列表。"""
        if not hits:
            return hits
        scores = self.score(query, [h["text"] for h in hits])
        order = np.argsort(-scores)
        out = []
        for i in order:
            h = dict(hits[int(i)])
            h["rerank_score"] = float(scores[int(i)])
            out.append(h)
        return out[:topk] if topk else out


if __name__ == "__main__":
    r = Reranker()
    q = "深渊有几个等级"
    docs = ["深渊纤维共分七级，宁静为入门级", "米玛塔尔共和国的历史可以追溯到……",
            "深渊可以三人进入，收益约为单巡洋的三倍"]
    for s, d in sorted(zip(r.score(q, docs), docs), reverse=True):
        print(f"  {s:>7.3f}  {d}")

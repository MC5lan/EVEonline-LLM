"""混合检索：向量 + BM25 + 英文硬词加权 + 邻块合并。

排序公式：
    score = α · norm(cosine) + (1-α) · norm(bm25) + 0.05 · (命中硬词数)

α 默认 0.55（略偏向量）。装上 bge-small-zh（ONNX）之后语义分可信，
向量占主导、BM25 兜住专有名词与型号编号。**

> 历史：在 hash 占位后端时期 α 曾压到 0.2，因为 hash 的稠密度分是碰撞噪声；
> 换成 bge 后调回 0.55。
向量模型则容易把它和 "T2" 混在一起。

邻块合并只在返回时拼接文本，不改动索引本身，所以可以安全地反复查询。
"""
from __future__ import annotations

import json
import pickle
import re
from pathlib import Path

import numpy as np

from rag.bm25 import BM25, ascii_terms, tokenize
from rag.embed import get_embedder
from rag.entities import EntityIndex

# 疑问/虚词：只用于标题匹配时的清洗，不参与 BM25 和向量
_QUESTION_WORDS = re.compile(r"怎么|如何|什么|哪个|哪些|多少|为什么|为何|区别|"
                             r"是什么|怎么样|请问|一下|吗|呢|的|，|。|\?|？")


def _norm(x: np.ndarray) -> np.ndarray:
    lo, hi = float(x.min()), float(x.max())
    if hi - lo < 1e-9:
        return np.zeros_like(x)
    return (x - lo) / (hi - lo)


def truncate(text: str, limit: int) -> str:
    """按句末边界截断，避免把一句话从中间砍断。"""
    if limit <= 0 or len(text) <= limit:
        return text
    cut = text[:limit]
    for p in "。！？\n；":
        i = cut.rfind(p)
        if i > limit * 0.5:
            return cut[: i + 1]
    return cut + "…"


# 舰种提问：「无畏级有几个高槽」问的是舰种，不是某一艘船。
# 只在「XX级」这种形式下触发，避免把「无畏刷怪」也判成舰种问题。
_CLASS_Q = re.compile(r"(无畏|战列巡洋|战列|巡洋|护卫|驱逐|战巡|泰坦|超级航母|航母|"
                      r"突击护卫|重型突击|拦截|隐形轰炸|战略巡洋)(级|舰)")

# 配船提问：问的是模块怎么装，不是船体属性
_FIT_Q = re.compile(r"配(船|装|置)|装配|配置|怎么配|装备什么")


class Retriever:
    def __init__(self, index_dir: str | Path = "index", alpha: float = 0.55):
        self.dir = Path(index_dir)
        meta_path = self.dir / "meta.json"
        if not meta_path.exists():
            raise SystemExit(f"{self.dir} 里没有索引，先跑 python -m rag.build_index")

        self.meta = json.loads(meta_path.read_text(encoding="utf-8"))
        self.chunks = [json.loads(l) for l in
                       (self.dir / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
                       if l.strip()]
        self.emb = np.load(self.dir / "emb.npy")
        if len(self.chunks) != self.emb.shape[0]:
            raise SystemExit("chunks 与 emb 数量不一致，索引可能损坏，请重建")

        self.alpha = alpha
        self.lower_texts = [c["text"].lower() for c in self.chunks]
        # 优先加载建索引时缓存的倒排表（3.6 万块可省 6-7 秒启动时间）；
        # 缓存缺失时现算。pkl 由本项目自己生成，不接受外部来源的 pickle。
        pkl = self.dir / "bm25.pkl"
        if pkl.exists():
            self.bm25 = pickle.loads(pkl.read_bytes())
        else:
            self.bm25 = BM25([tokenize(c["text"]) for c in self.chunks])
        self.embedder = get_embedder(self.meta.get("provider", "st"),
                                     self.meta.get("model", ""),
                                     self.meta.get("dim", 1024))

        # 舰种索引的块，用于回答「XX级」这类舰种提问
        cm = np.array(["舰种索引" in (c.get("source") or "") for c in self.chunks])
        self.class_mask = cm if cm.any() else None
        # 装配库的块，用于回答「怎么配」
        fm = np.array(["装配库" in (c.get("source") or "") for c in self.chunks])
        self.fitting_mask = fm if fm.any() else None

        # 实体表是可选增强：没有它检索照常工作，只是专有名词精度差一些
        self.entities = EntityIndex()
        self.card_by_name: dict[str, list[int]] = {}
        for i, c in enumerate(self.chunks):
            src = c.get("source", "")
            if src.startswith("sde_cards:"):
                self.card_by_name.setdefault(src.split(":", 1)[1], []).append(i)

        # 权重：先在层级上乘（官方/攻略/百科/剧情…），再按来源子串覆盖。
        # 只在排序时乘系数，不改索引内容，所以调参数不用重建。
        self.weight_rules: dict[str, float] = {}
        self.chunk_weights = np.ones(len(self.chunks), dtype=np.float32)
        wpath = Path(__file__).resolve().parent.parent / "data" / "source_weights.json"
        if wpath.exists():
            try:
                raw = json.loads(wpath.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                raw = {}

            tiers = raw.get("_tiers") or {}
            tier_arr = np.array([c.get("tier") or "" for c in self.chunks])
            for t, w in tiers.items():
                if not isinstance(w, (int, float)):
                    continue
                mask = tier_arr == t
                if mask.any():
                    self.chunk_weights[mask] = float(w)
                    self.weight_rules[f"tier:{t}"] = float(w)

            # 时效：2014 年的攻略和 2026 年的攻略平权是不合理的。
            # 年份取自 curate.py（文件名/正文里的 20xx），未知年给一个小折扣。
            year_arr = np.array([int(c.get("year") or 0) for c in self.chunks])
            for band in (raw.get("_year_bands") or []):
                try:
                    limit, w = int(band[0]), float(band[1])
                except (TypeError, ValueError, IndexError):
                    continue
                mask = (year_arr > 0) & (year_arr <= limit)
                if mask.any():
                    self.chunk_weights[mask] *= w
                    self.weight_rules[f"year<={limit}"] = w
            unknown = year_arr == 0
            if unknown.any():
                self.chunk_weights[unknown] *= 0.95

            # 与 SDE 冲突的块：不删，只降权
            if any(c.get("stale") for c in self.chunks):
                stale_mask = np.array([bool(c.get("stale")) for c in self.chunks])
                self.chunk_weights[stale_mask] *= 0.8
                self.weight_rules["stale"] = 0.8

            for k, v in raw.items():
                if k.startswith("_") or not isinstance(v, (int, float)):
                    continue
                mask = np.fromiter((k in c.get("source", "") for c in self.chunks),
                                   dtype=bool, count=len(self.chunks))
                if mask.any():
                    self.chunk_weights[mask] *= float(v)
                    self.weight_rules[k] = float(v)

        # 文件名不进正文，所以「无畏刷怪基础教程.md」里的段落天然拿不到标题分。
        # 预先把来源名切好词，查询时按重叠比例补一点分——文档的标题往往就是
        # 它最好的主题标签。
        self.source_tokens = [set(tokenize(Path(c.get("source", "")).stem))
                              for c in self.chunks]

    # ---------------------------------------------------------------- 实体
    def entities_in(self, query: str) -> list[dict]:
        return self.entities.find(query)

    def _entity_indices(self, ents: list[dict]) -> list[int]:
        out: list[int] = []
        for e in ents:
            for key in (e.get("zh"), e.get("en")):
                if key and key in self.card_by_name:
                    out.extend(self.card_by_name[key])
                    break
        return out

    # ---------------------------------------------------------------- 向量
    def _encode_query(self, query: str) -> np.ndarray:
        return self.embedder.encode([query], is_query=True)[0]

    # ---------------------------------------------------------------- 检索
    def search(self, query: str, k: int = 3, expand: bool = True) -> list[dict]:
        ents = self.entities_in(query)
        # 识别到实体就把它的中英文名补进查询：玩家写「多米尼克斯级」，
        # 攻略里可能写 Dominix，补全后 BM25 才能同时命中两种写法。
        q = self.entities.expand(query, ents)

        qv = self._encode_query(q)
        dense = self.emb @ qv                                   # 已归一化 => 余弦
        sparse = self.bm25.scores(tokenize(q))

        score = self.alpha * _norm(dense) + (1 - self.alpha) * _norm(sparse)

        # 来源降权放在加成之前：剧情文本不该靠"提过一次舰船名"就压过攻略。
        if self.weight_rules:
            score = score * self.chunk_weights

        for t in ascii_terms(q):
            hit = np.fromiter((t in txt for txt in self.lower_texts),
                              dtype=np.float32, count=len(self.lower_texts))
            score += 0.05 * hit

        # 标题加成：文件名里命中查询词的比例越高，越可能是"讲这件事的那篇"。
        # 先剔除疑问词再切词，否则「无畏刷怪怎么配装」里的"怎么/配装"会稀释
        # 真正有区分度的「无畏」「刷怪」，标题匹配的分就上不去。
        qtok = set(tokenize(_QUESTION_WORDS.sub("", query)))
        if qtok:
            ratio = np.fromiter(
                (len(qtok & st) / len(qtok) for st in self.source_tokens),
                dtype=np.float32, count=len(self.source_tokens))
            score += 0.25 * ratio

        # 实体硬锁定：权重 0.5 远大于其它加成，确保问哪艘船就出哪艘船的卡。
        # 但「多米尼克斯级」是「多米尼克斯级海军型」的前缀，两者都会命中；
        # 对后者（名称被拉长的衍生型）只给一半加成，让基础型排前面。
        if ents:
            boosted = self._entity_indices(ents)
            if boosted:
                score[boosted] += 0.5
                for e in ents:
                    name = e.get("matched") or e.get("name") or ""
                    if len(name) < 3:
                        continue
                    # 允许中间夹一个「级」：实体可能是「多米尼克斯」，
                    # 而卡名是「多米尼克斯级海军型」。
                    pat = re.compile(re.escape(name) + r"级?(海军型|舰队型|帝国型|II|守卫|警察型)")
                    idx = np.fromiter(
                        (bool(pat.search(self.chunks[i]["text"])) for i in boosted),
                        dtype=bool, count=len(boosted))
                    score[np.asarray(boosted)[idx]] -= 0.25

        # 舰种提问：只给「讲这个舰种的那一段」升权。
        # 整个索引都加权的话，49 个舰种平权，照样会捞到别的舰种。
        cq = _CLASS_Q.search(query)
        if cq and self.class_mask is not None:
            term = cq.group(1)
            idx = np.where(self.class_mask)[0]
            # 只认「标题就是这个舰种」的块：「枪骑兵级无畏舰」也含「无畏」，
            # 但它不是无畏舰这个舰种，模糊包含会把它们混为一谈。
            def _head(t: str) -> str:
                h = t.split("（")[0].replace("#", "").strip()
                return h

            hit = np.array([_head(self.chunks[i]["text"]) in (term + "舰", term)
                            for i in idx])
            if hit.any():
                score[idx[hit]] += 0.9
            else:
                score[self.class_mask] += 0.4

        # 配船提问：问的是「怎么配」，答案在装配库而不是舰船卡。
        # 舰船卡给的是船体属性，配装要看具体模块，两者不能混。
        if ents and _FIT_Q.search(query):
            names = [e.get("matched") or e.get("name") or "" for e in ents]
            idx = np.where(self.fitting_mask)[0] if self.fitting_mask is not None else []
            if len(idx):
                hit = np.array([any(n and n in self.chunks[i]["text"] for n in names)
                                for i in idx])
                if hit.any():
                    score[idx[hit]] += 0.8

        order = np.argsort(-score)[: max(k * 3, k)]
        selected = [int(i) for i in order[:k]]

        groups = self._group(selected) if expand else [[i] for i in selected]

        out = []
        for g in groups:
            out.append({
                "id": g[0],
                "ids": g,
                "text": "\n\n".join(self.chunks[i]["text"] for i in g),
                "source": self.chunks[g[0]]["source"],
                "pos": self.chunks[g[0]]["pos"],
                "score": float(max(score[i] for i in g)),
            })
        out.sort(key=lambda x: -x["score"])
        return out

    def _group(self, ids: list[int]) -> list[list[int]]:
        """同一文档里编号连续的块合成一组，避免上下文被切断。"""
        if not ids:
            return []
        by_doc: dict[int, list[int]] = {}
        for i in ids:
            by_doc.setdefault(self.chunks[i]["doc_id"], []).append(i)

        groups: list[list[int]] = []
        for _, group in by_doc.items():
            group = sorted(group)
            run = [group[0]]
            for j in group[1:]:
                if j == run[-1] + 1:
                    run.append(j)
                else:
                    groups.append(run)
                    run = [j]
            groups.append(run)
        return groups


PROMPT_HEAD = "你是 EVE Online 中文助手。下面是从资料库检索到的片段。\n\n"

PROMPT_TAIL = (
    "\n用户问题：{q}\n\n"
    "回答要求：\n"
    "1. 只依据上面的资料作答，不要补充资料以外的内容。\n"
    "2. 资料里没有的信息，直接回答「资料中没有提到」。\n"
    "3. 保留英文术语与缩写（MWD、T3C、ISK、EHP）。\n"
    "4. 直接给答案，不要复述问题，不要写「根据资料」。\n"
    "5. 回答控制在三句话以内。\n"
)

# 引用由程序回填（见 rag/ask.py），所以这里刻意不让模型输出 [1]。
# 76M 参数同时学「找答案」和「数编号」会显著降低准确率。


def build_prompt(query: str, hits: list[dict], chunk_chars: int = 300) -> str:
    blocks = []
    for n, h in enumerate(hits, 1):
        blocks.append(f"【资料{n}】来源：{h['source']}\n"
                      f"{truncate(h['text'], chunk_chars)}")
    return PROMPT_HEAD + "\n\n".join(blocks) + PROMPT_TAIL.format(q=query)

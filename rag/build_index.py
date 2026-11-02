"""把 EVE 语料切成块并建索引。

产物（index/ 目录）：
  chunks.jsonl   每行一个块：{id, text, source, doc_id, pos}
  emb.npy        float32 [N, D]，已 L2 归一化，直接点积即余弦
  meta.json      provider / 模型名 / 维度 / 块数 / 构建时间

为什么块要 500 字符左右：
  * 太短（<200）：切碎上下文，检索到的碎片读不懂
  * 太长（>1000）：一个块里混进多个主题，向量被平均掉，召回下降
  500 是中文技术文档的经验甜点，邻块会在检索时合并回来。

用法：
  python -m rag.build_index --input D:/Game/eve_raw --out index
  python -m rag.build_index --input data/domain.txt --out index --provider hash  # 无 torch 时测管道
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path

import numpy as np

MIRROR = "https://hf-mirror.com"

_HTML = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\u3000]+")

# 分类文件夹的文件头（沿用人工清洗库的规范）
_FM = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
DOMAIN_META = {
    "01": ("新手", "攻略"), "02": ("装配", "攻略"), "03": ("战斗", "攻略"),
    "04": ("任务", "攻略"), "05": ("生产", "攻略"), "06": ("机制", "攻略"),
    "07": ("市场", "攻略"), "08": ("剧情", "剧情"), "09": ("百科", "百科"),
    "10": ("工具", "工具"), "11": ("组织", "攻略"), "99": ("杂项", "其他"),
}


def split_fm(raw: str) -> tuple[dict, str]:
    m = _FM.match(raw)
    if not m:
        return {}, raw
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta, raw[m.end():]


def clean(raw: str) -> str:
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    raw = _HTML.sub("", raw)
    raw = (raw.replace("&nbsp;", " ").replace("&amp;", "&")
              .replace("&lt;", "<").replace("&gt;", ">"))
    lines = [_WS.sub(" ", ln).strip() for ln in raw.split("\n")]
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def paragraphs(text: str, min_len: int = 40):
    for p in re.split(r"\n\s*\n", text):
        p = p.strip()
        if len(p) >= min_len:
            yield p


def split_long(p: str, target: int) -> list[str]:
    """把超长段落按句末切开。

    为什么必须做：PDF/Word 抽出来的正文常常整页只有换行、没有空行，
    于是"一个段落"就是 2000 字。不切开的话，切块函数会把它整段吞下去，
    最终块平均长度远超目标，向量被平均掉，检索精度直接掉一半。

    没有标点的长串（表格、英文清单）按硬长度兜底切，否则会出现上万字的块。
    """
    if len(p) <= target * 1.5:
        return [p]
    sents = re.split(r"(?<=[。！？!?\n])", p)
    out: list[str] = []
    buf = ""
    for s in sents:
        if not s:
            continue
        if buf and len(buf) + len(s) > target:
            out.append(buf)
            buf = ""
        buf += s
        while len(buf) > target * 2:
            out.append(buf[:target])
            buf = buf[target:]
    if buf:
        out.append(buf)
    return [x for x in out if x.strip()]


def is_table(text: str) -> bool:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 3:
        return False
    t = sum(1 for ln in lines if ln.lstrip().startswith("|"))
    return t / len(lines) > 0.6


_TOC_LINE = re.compile(r"[.．]{4,}")
_FIT_ITEM = re.compile(r"\d+\s*[xX×]")


def is_toc(text: str) -> bool:
    """目录页：一堆「章节名......页码」。

    这类块对检索毫无价值，还会污染结果（问什么都能命中，因为目录里什么都有）。
    通读时发现索引里混了 200 多块纯目录，直接丢掉。
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 3:
        return False
    t = sum(1 for ln in lines if _TOC_LINE.search(ln))
    return t / len(lines) > 0.3


def is_fitting(text: str) -> bool:
    """装配清单：反复出现「2x 模块名」。

    它不是散文，是结构化数据（槽位 → 装了什么）。当散文索引会彼此干扰，
    但内容本身有价值，所以只打标记不删除，供后续单独处理。
    """
    if len(_FIT_ITEM.findall(text)) < 3:
        return False
    return any(k in text for k in ("高槽", "中槽", "低槽", "高能量槽", "中能量槽", "低能量槽"))


def chunk_kind(text: str) -> str:
    if is_fitting(text):
        return "fitting"
    if is_table(text):
        return "table"
    return "text"


def norm_key(text: str) -> str:
    """去空白与标点后的哈希：抓「转换器不同但内容相同」的近似重复。

    正文 md5 只能抓一字不差；PDF 与 Word 转出来的同一篇，标点和换行必然不同，
    要靠归一化才能认出来。
    """
    s = re.sub(r"[\s，。、；：！？,.;:!?\"'`（）()\[\]【】<>《》—\-…·|]", "", text)
    return hashlib.md5(s.encode("utf-8", "ignore")).hexdigest()


def chunk(paras: list[str], target: int = 500, overlap: int = 1) -> list[str]:
    flat: list[str] = []
    for p in paras:
        flat.extend(split_long(p, target))
    paras = flat

    chunks: list[str] = []
    buf: list[str] = []
    n = 0
    for p in paras:
        if n + len(p) > target and buf:
            chunks.append("\n\n".join(buf))
            buf = buf[-overlap:] if overlap else []
            n = sum(len(x) for x in buf)
        buf.append(p)
        n += len(p)
    if buf:
        chunks.append("\n\n".join(buf))
    return [c for c in chunks if len(c) >= 80]


def collect(input_paths, meta_map: dict | None = None,
            stale: set | None = None) -> tuple[list[dict], int]:
    """支持多个输入。.jsonl 里每行一条 {"text": ...}，一行就是一块，不再切分。

    SDE 卡片走的就是 jsonl 这条路：一张卡是一个完整实体，
    切碎反而会破坏"名称 + 分类 + 属性"的对应关系。

    meta_map 由 tools/curate.py 产出，给每个文档带上 category / tier / year，
    检索时就能按类别路由、按时效降权，而不是按文件名瞎猜。
    """
    meta_map = meta_map or {}
    stale = stale or set()
    if isinstance(input_paths, (str, Path)):
        input_paths = [input_paths]

    files: list[Path] = []
    for p in input_paths:
        p = Path(p)
        if p.is_dir():
            files.extend(sorted(x for x in p.rglob("*")
                                if x.suffix.lower() in {".txt", ".md", ".html", ".htm", ".jsonl"}
                                and x.name not in ("_README.md", "_index.md")))
        elif p.exists():
            files.append(p)

    rows: list[dict] = []
    cid = 0
    seen_text: set[str] = set()
    n_dup = 0
    n_toc = 0
    n_skip = 0
    for doc_id, fp in enumerate(files):
        if fp.suffix.lower() == ".jsonl":
            with fp.open(encoding="utf-8") as f:
                for n, line in enumerate(f):
                    line = line.strip()
                    if not line or '"text"' not in line:
                        continue
                    try:
                        o = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    t = (o.get("text") or "").strip()
                    if len(t) < 40:
                        continue
                    h = hashlib.md5(t.encode("utf-8", "ignore")).hexdigest()
                    if h in seen_text:
                        n_dup += 1
                        continue
                    seen_text.add(h)
                    rows.append({"id": cid, "text": t,
                                 "source": f"{fp.stem}:{o.get('name', n)}",
                                 "doc_id": doc_id, "pos": n, "kind": "card",
                                 "category": "物品", "tier": "官方", "year": "",
                                 "stale": False})
                    cid += 1
            continue

        try:
            raw = fp.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        # 分类文件夹的文档自带 YAML 头：domain/subdomain/accuracy/freshness。
        # 头必须剥掉，否则会被当成正文索引；同时它是比启发式更准的分类来源。
        fm, body = split_fm(raw)
        text = clean(body)
        if len(text) < 100:
            continue
        # 同一份内容常常同时存在于多个来源目录（eve_raw 转出的攻略与知识库里
        # 的同名文件）。按正文哈希去重，否则会白占两成索引、还在结果里重复出现。
        m = meta_map.get(fp.name, {})
        if fm.get("domain"):
            cat, tier = DOMAIN_META.get(fm["domain"][:2], ("其他", "其他"))
        else:
            cat, tier = m.get("category", "其他"), m.get("tier", "其他")
        acc = fm.get("accuracy", "")
        sub = fm.get("subdomain", "")
        # 重写稿（canonical）优先于原始素材：它已经对齐当前 SDE、去重、统一术语
        if fm.get("type") == "canonical":
            tier = "权威"
        elif fp.name == "source.md":
            # 每个 canonical 文件夹里的原文。corpus/ 已移除，原文只存在于这里，
            # 必须入索引，但权重低于重写稿。
            tier = "原文"
        # 人工判定为「冗余SDE」或「无正文」的文档不进索引：
        # 它们不提供新信息，只会稀释检索结果。文件仍保留在 corpus 里可查。
        verdict = fm.get("ai_verdict", "")
        if verdict in ("redundant", "invalid"):
            n_skip += 1
            continue
        # 尚未重写的占位稿不进索引
        if fm.get("type") == "placeholder":
            n_skip += 1
            continue
        # canonical 目录下一律是 rewrite.md / source.md，直接用文件名会让所有
        # 条目都叫 rewrite.md，出处就丢了。用文件夹名作为来源。
        src_name = fp.parent.name if fp.name in ("rewrite.md", "source.md") else fp.name

        # 已被结构化替代的原始文件（如装配原件）在 meta.yaml 里标 index: false，
        # 不再入索引，否则原始堆料会盖过解析后的条目。
        if fp.name in ("rewrite.md", "source.md"):
            mp = fp.parent / "meta.yaml"
            if mp.exists() and "index: false" in mp.read_text(encoding="utf-8"):
                n_skip += 1
                continue
        for pos, c in enumerate(chunk(list(paragraphs(text)))):
            if is_toc(c):
                n_toc += 1
                continue
            h = norm_key(c)
            if h in seen_text:
                n_dup += 1
                continue
            seen_text.add(h)
            rows.append({"id": cid, "text": c, "source": src_name,
                         "doc_id": doc_id, "pos": pos, "kind": chunk_kind(c),
                         "category": cat, "tier": tier,
                         "subdomain": sub, "accuracy": acc,
                         "year": m.get("year", ""),
                         "stale": (fp.name, pos) in stale})
            cid += 1

    if n_dup:
        print(f"[index] 去重跳过 {n_dup:,} 个重复块")
    if n_toc:
        print(f"[index] 丢弃 {n_toc:,} 个目录块")
    if n_skip:
        print(f"[index] 按判定排除 {n_skip:,} 篇（冗余/无正文）")
    return rows, len(files)


def build(input_path, out_dir: str | Path, provider: str = "st",
          model: str = "", batch: int = 64, target: int = 500,
          dim: int = 1024, curation: str | Path | None = None,
          conflicts: str | Path | None = None) -> dict:
    """可编程调用的建索引入口（测试直接调它，不走 CLI）。"""
    srcs = input_path if isinstance(input_path, (list, tuple)) else [input_path]
    for s in srcs:
        if not Path(s).exists():
            raise SystemExit(f"输入不存在: {s}")

    meta_map: dict[str, dict] = {}
    if curation and Path(curation).exists():
        with open(curation, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                o = json.loads(line)
                if o.get("status") == "ok" and o.get("out"):
                    meta_map[o["out"]] = o
        print(f"[index] 已加载分类信息 {len(meta_map)} 篇")

    # 交叉验证的结论反过来标进索引：与 SDE 冲突的块打 stale 标记，检索时降权
    stale: set[tuple] = set()
    if conflicts and Path(conflicts).exists():
        with open(conflicts, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                o = json.loads(line)
                stale.add((o.get("source"), o.get("pos")))
        print(f"[index] 已加载冲突标记 {len(stale)} 处")

    t0 = time.time()
    rows, n_files = collect(srcs, meta_map, stale)
    if not rows:
        raise SystemExit("没有切出任何块，检查输入是不是空的")
    avg = sum(len(r["text"]) for r in rows) / len(rows)
    print(f"[index] {n_files} 个文件 -> {len(rows)} 块（平均 {avg:.0f} 字符）")
    cats = {}
    for r in rows:
        cats[r.get("tier", "?")] = cats.get(r.get("tier", "?"), 0) + 1
    print("[index] 层级分布：" + "  ".join(f"{k}={v:,}" for k, v in
                                          sorted(cats.items(), key=lambda x: -x[1])))

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "chunks.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # BM25 的倒排表在 3.6 万块上要切词 6-7 秒，每次启动都重算太浪费。
    # 建索引时算一次存盘，查询时直接加载。
    import pickle

    from rag.bm25 import BM25, tokenize
    t_bm = time.time()
    bm = BM25([tokenize(r["text"]) for r in rows])
    (out / "bm25.pkl").write_bytes(pickle.dumps(bm, protocol=4))
    print(f"[index] BM25 倒排表已缓存（{time.time()-t_bm:.1f}s，"
          f"{(out/'bm25.pkl').stat().st_size/1024/1024:.0f} MB）")

    from rag.embed import get_embedder
    embedder = get_embedder(provider, model, dim)
    print(f"[index] 向量化 provider={provider}"
          f"{' model=' + model if provider == 'st' and model else ''}")
    emb = embedder.encode([r["text"] for r in rows], is_query=False)
    np.save(out / "emb.npy", emb)

    meta = {
        "provider": provider,
        "model": model or (embedder.model_name if provider == "st" else "hash"),
        "dim": int(emb.shape[1]),
        "n_chunks": len(rows),
        "n_files": n_files,
        "target_chars": target,
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_s": round(time.time() - t0, 1),
    }
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
    print(f"[index] 完成：{emb.shape} -> {out}（{meta['elapsed_s']}s）")
    return meta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, nargs="+",
                    help="一个或多个来源：目录、txt、jsonl（SDE 卡片）")
    ap.add_argument("--out", default="index")
    ap.add_argument("--provider", default="bge", choices=["bge", "st", "hash"])
    ap.add_argument("--model", default="", help="st 的模型名，留空用 bge-small-zh")
    ap.add_argument("--dim", type=int, default=1024, help="hash 的维度")
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--target", type=int, default=500, help="块目标字符数")
    ap.add_argument("--curation", default="data/curated.jsonl",
                    help="tools/curate.py 产出的分类清单")
    ap.add_argument("--conflicts", default="data/conflicts.jsonl",
                    help="tools/crosscheck.py 产出的冲突清单")
    ap.add_argument("--hf-endpoint", default=MIRROR)
    args = ap.parse_args()

    os.environ.setdefault("HF_ENDPOINT", args.hf_endpoint)
    build(args.input, args.out, args.provider, args.model,
          args.batch, args.target, args.dim, args.curation, args.conflicts)


if __name__ == "__main__":
    main()

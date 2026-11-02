"""清洗 EVE 语料：去 HTML、去样板行、段级去重、规范空白。

输入可以是一个目录（递归读 .txt/.md/.html）或单个文件。
输出是纯文本，段落之间空行，文档之间用一行 `<|eos|>` 分隔。

为什么段级去重是必须的：
EVE wiki 和论坛里大量内容是从同一份模板复制的（舰船页的槽位说明、
装备页的属性表）。不去重的话，这些段落会被训练几十遍，
模型会疯狂地重复输出它们。

用法：
  python scripts/prepare_domain.py --input D:/Game/eve_raw --out data/domain.txt
"""
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

from tqdm import tqdm

# 论坛/wiki 常见的样板行
BOILERPLATE = re.compile(
    r"^(版权|版权所有|copyright|all rights reserved|转载请注明|本文来自|"
    r"点击查看|上一篇|下一篇|相关阅读|返回顶部|登录|注册|首页|"
    r"advertisement|分享到|扫一扫|关注我们)",
    re.I,
)

HTML_TAG = re.compile(r"<[^>]+>")
MULTI_SPACE = re.compile(r"[ \t\u3000]+")
MULTI_NL = re.compile(r"\n{3,}")


def simhash(text: str, bits: int = 64) -> int:
    """字符 3-gram 的 simhash，用于近重复检测。"""
    if len(text) < 10:
        return 0
    v = [0] * bits
    for i in range(len(text) - 2):
        h = int(hashlib.md5(text[i : i + 3].encode("utf-8", "ignore")).hexdigest()[:16], 16)
        for b in range(bits):
            v[b] += 1 if (h >> b) & 1 else -1
    out = 0
    for b in range(bits):
        if v[b] > 0:
            out |= 1 << b
    return out


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def clean_text(raw: str) -> str:
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    raw = HTML_TAG.sub("", raw)
    raw = raw.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")

    lines = []
    for line in raw.split("\n"):
        s = line.strip()
        if not s:
            lines.append("")
            continue
        if BOILERPLATE.match(s):
            continue
        s = MULTI_SPACE.sub(" ", s)
        lines.append(s)

    text = "\n".join(lines)
    text = MULTI_NL.sub("\n\n", text)
    return text.strip()


def iter_paragraphs(text: str):
    for p in re.split(r"\n\s*\n", text):
        p = p.strip()
        if len(p) >= 60:          # 太短的片段（导航、标题）丢掉
            yield p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="目录或单个文件")
    ap.add_argument("--out", required=True)
    ap.add_argument("--near-dup-threshold", type=int, default=3,
                    help="simhash 汉明距离小于该值视为重复")
    args = ap.parse_args()

    src = Path(args.input)
    if src.is_dir():
        files = sorted([p for p in src.rglob("*")
                        if p.suffix.lower() in {".txt", ".md", ".html", ".htm"}])
    else:
        files = [src]

    if not files:
        raise SystemExit(f"{src} 下没有可读的 .txt/.md/.html 文件")

    print(f"[prepare] 待处理 {len(files)} 个文件")

    seen_exact: set[int] = set()
    kept_hashes: list[int] = []
    kept_chars = 0
    dropped_exact = dropped_near = 0

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    with open(out, "w", encoding="utf-8") as f:
        for fp in tqdm(files, desc="清洗"):
            try:
                raw = fp.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            text = clean_text(raw)
            if len(text) < 100:
                continue

            doc_paras = []
            for p in iter_paragraphs(text):
                h = int(hashlib.md5(p.encode("utf-8", "ignore")).hexdigest()[:16], 16)
                if h in seen_exact:
                    dropped_exact += 1
                    continue
                seen_exact.add(h)

                sh = simhash(p)
                if any(hamming(sh, k) < args.near_dup_threshold for k in kept_hashes[-4000:]):
                    dropped_near += 1
                    continue
                kept_hashes.append(sh)
                doc_paras.append(p)

            if doc_paras:
                f.write("\n\n".join(doc_paras))
                f.write("\n\n<|eos|>\n\n")
                kept_chars += sum(len(p) for p in doc_paras)

    print(f"[prepare] 保留 {kept_chars:,} 字符")
    print(f"[prepare] 丢弃 完全重复 {dropped_exact} 段 / 近重复 {dropped_near} 段")
    print(f"[prepare] 输出 -> {out}")
    if kept_chars < 1_000_000:
        print("⚠️  清洗后不足 100 万字符，SFT 数据量会很有限，建议补充语料来源")


if __name__ == "__main__":
    main()

"""语料体检：在动手清洗之前，先看清你的 300 万字符到底是什么样。

只用标准库，不需要 torch / numpy，任何 Python 3.9+ 都能跑。
把语料丢进 D:/Game/eve_raw 之后，一条命令就能知道该花多少工夫在清洗上。

它会告诉你：
  * 总量、文件分布、编码问题
  * HTML 残留、超短文件（模板页）
  * 段落数、平均长度、被丢弃的碎段落比例
  * 重复段落率（精确 + 首尾指纹），决定要去掉多少水
  * 预估切块数，决定向量索引的规模
  * EVE 术语覆盖率，判断语料是不是真的够专业

用法：
  python tools/audit_corpus.py --input D:/Game/eve_raw
  python tools/audit_corpus.py --selftest
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

EXTS = {".txt", ".md", ".html", ".htm"}
TERMS = ["MWD", "AB", "T3C", "T2", "ISK", "EHP", "HAC", "LP", "PLEX",
         "虫洞", "装配", "抗性", "无人机", "信号半径", "盖伦特", "加达里"]

# 只认真正的标签名。用 <[^>]+> 会把握手式的中文占位符（<玩家名>）、
# 比较表达式（A<B）全部误判成 HTML —— 实测一次虚报了 2 万多个"标签"。
_HTML_TAG = re.compile(r"</?[a-zA-Z][a-zA-Z0-9]{0,12}(\s[^<>]{0,200})?/?>")
_CJK = re.compile(r"[\u4e00-\u9fff]")
_ASCII = re.compile(r"[A-Za-z]")
_WS = re.compile(r"\s+")


def read_text(fp: Path) -> tuple[str, str]:
    """返回 (文本, 使用的编码)。UTF-8 失败时退回 GBK，再不行就忽略错误。"""
    raw = fp.read_bytes()
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore"), "utf-8(ignore)"


def norm(p: str) -> str:
    return _WS.sub("", p).strip()


def fingerprint(p: str) -> str:
    """首尾各 40 字的指纹，用来抓模板化段落（页眉、属性表头）。"""
    s = norm(p)
    return hashlib.md5((s[:40] + "|" + s[-40:]).encode("utf-8", "ignore")).hexdigest()


def audit(root: Path) -> dict:
    files = sorted(p for p in root.rglob("*") if p.suffix.lower() in EXTS) if root.is_dir() else [root]
    if not files:
        raise SystemExit(f"{root} 下没有 .txt/.md/.html 文件")

    stats = {
        "root": str(root),
        "files": len(files),
        "chars": 0,
        "by_ext": Counter(),
        "encodings": Counter(),
        "html_files": 0,
        "html_tags": 0,
        "short_files": 0,
        "empty_files": 0,
        "paragraphs": 0,
        "short_paragraphs": 0,
        "para_lens": [],
        "dup_paragraphs": 0,
        "dup_chars": 0,
        "cjk": 0,
        "ascii": 0,
        "terms": Counter(),
        "big_files": [],
    }

    seen_norm: set[str] = set()
    seen_fp: set[str] = set()

    for fp in files:
        try:
            text, enc = read_text(fp)
        except OSError:
            continue
        stats["encodings"][enc] += 1
        stats["by_ext"][fp.suffix.lower()] += 1
        stats["chars"] += len(text)
        if len(text.strip()) < 100:
            stats["short_files"] += 1
        if not text.strip():
            stats["empty_files"] += 1
        if fp.stat().st_size > 2_000_000:
            stats["big_files"].append(fp.name)

        tags = _HTML_TAG.findall(text)
        if tags:
            stats["html_files"] += 1
            stats["html_tags"] += len(tags)

        stats["cjk"] += len(_CJK.findall(text))
        stats["ascii"] += len(_ASCII.findall(text))
        for t in TERMS:
            stats["terms"][t] += text.count(t)

        for p in re.split(r"\n\s*\n", text):
            p = p.strip()
            if not p:
                continue
            stats["paragraphs"] += 1
            stats["para_lens"].append(len(p))
            if len(p) < 40:
                stats["short_paragraphs"] += 1
                continue
            n = norm(p)
            if n in seen_norm:
                stats["dup_paragraphs"] += 1
                stats["dup_chars"] += len(p)
                continue
            seen_norm.add(n)
            f = fingerprint(p)
            if f in seen_fp:
                stats["dup_paragraphs"] += 1
                stats["dup_chars"] += len(p)
            else:
                seen_fp.add(f)

    lens = stats.pop("para_lens")
    kept = len(lens) - stats["short_paragraphs"]
    stats["avg_para_len"] = round(sum(lens) / max(1, len(lens)), 1)
    stats["short_para_rate"] = round(stats["short_paragraphs"] / max(1, stats["paragraphs"]), 3)
    stats["dup_rate"] = round(stats["dup_chars"] / max(1, stats["chars"]), 3)
    stats["clean_chars"] = stats["chars"] - stats["dup_chars"]
    stats["est_chunks"] = max(1, round(stats["clean_chars"] / 500))
    stats["est_tokens"] = round(stats["clean_chars"] * 0.7)
    stats["files_with_terms"] = sum(1 for t, c in stats["terms"].items() if c > 0)
    stats["by_ext"] = dict(stats["by_ext"])
    stats["encodings"] = dict(stats["encodings"])
    stats["terms"] = dict(stats["terms"])
    stats["kept_paragraphs"] = kept
    return stats


def report(s: dict) -> None:
    print("=" * 56)
    print(f"语料体检：{s['root']}")
    print("=" * 56)
    print(f"文件数        {s['files']}   类型 {s['by_ext']}")
    print(f"总字符        {s['chars']:,}")
    print(f"编码          {s['encodings']}")
    print(f"中文字符      {s['cjk']:,}   英文 {s['ascii']:,}")
    print(f"段落          {s['paragraphs']:,}（平均 {s['avg_para_len']} 字）")
    print(f"碎段落(<40字)  {s['short_paragraphs']:,}  占 {s['short_para_rate']:.1%}")
    print(f"重复段落       {s['dup_paragraphs']:,}  占字符 {s['dup_rate']:.1%}")
    print(f"清洗后字符     {s['clean_chars']:,}")
    print(f"预估块数       {s['est_chunks']:,}（按 500 字符/块）")
    print(f"预估 tokens    {s['est_tokens']:,}")
    print("-" * 56)
    print(f"HTML 残留文件  {s['html_files']}  标签 {s['html_tags']:,}")
    print(f"超短文件       {s['short_files']}   空文件 {s['empty_files']}")
    if s["big_files"]:
        print(f"超大文件(>2MB) {s['big_files'][:3]}")
    print("-" * 56)
    print("EVE 术语覆盖：")
    hit = sorted(s["terms"].items(), key=lambda x: -x[1])
    for t, c in hit:
        flag = " " if c else "  ← 缺"
        print(f"  {t:<10} {c:>6}{flag}")
    print("-" * 56)

    print("结论：")
    if s["dup_rate"] > 0.25:
        print(f"  ⚠ 重复率 {s['dup_rate']:.0%} 偏高，必须先跑 prepare_domain.py 去重，")
        print("    否则模型会把这些段落背得滚瓜烂熟。")
    if s["short_para_rate"] > 0.5:
        print("  ⚠ 碎段落超过一半，说明多是列表/表格。建议先合并相邻短行再切块。")
    if s["html_files"] and s["html_tags"] / max(1, s["files"]) > 20:
        print("  ⚠ HTML 标签很多，清洗时务必剥干净。")
    if s["files_with_terms"] < 8:
        print("  ⚠ 只有少数几个 EVE 术语出现，语料可能不够专业，或术语写法不统一。")
    if s["clean_chars"] < 1_000_000:
        print("  ⚠ 清洗后不足 100 万字符，SFT 数据会很有限。")
    print(f"  建议：先去重 -> 切块 {s['est_chunks']} 个 -> 向量索引约 "
          f"{s['est_chunks'] * 512 * 4 / 1024 / 1024:.0f} MB")
    print("=" * 56)


def selftest() -> int:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        dup = ("MWD 会显著增大舰船的信号半径，这是它最大的代价，"
               "也是玩家在交战时最需要权衡的一点。")
        (root / "a.txt").write_text(
            f"{dup}\n\n{dup}\n\nAB 不会增大信号半径，因此在需要隐蔽时更合适一些。",
            encoding="utf-8")
        (root / "b.html").write_text(
            "<div>T3C 由四个子系统组成，这是 EVE 的机制。</div>\n\n"
            "<p>ISK 是 EVE 的货币，玩家用它交易舰船。</p>", encoding="utf-8")
        (root / "c.md").write_text("短", encoding="utf-8")

        s = audit(root)
        fails = []
        if s["files"] != 3:
            fails.append(f"文件数 {s['files']} != 3")
        if s["dup_paragraphs"] < 1:
            fails.append("重复段落没被抓到")
        if s["html_tags"] < 2:
            fails.append("HTML 标签没被抓到")
        if s["short_files"] < 1:
            fails.append("超短文件没被抓到")
        if s["terms"].get("MWD", 0) < 2:
            fails.append("术语计数错误")

        if fails:
            for f in fails:
                print(f"  [FAIL] {f}")
            return 1
        print("  [ok]  selftest 通过：重复 / HTML / 超短文件 / 术语计数 均正确")
        return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=None, help="语料目录")
    ap.add_argument("--json", default=None, help="把结果另存为 JSON")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())

    if not args.input:
        ap.error("需要 --input 或 --selftest")
    root = Path(args.input)
    if not root.exists():
        sys.exit(f"输入不存在: {root}")

    stats = audit(root)
    report(stats)
    if args.json:
        Path(args.json).write_text(json.dumps(stats, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
        print(f"已保存 -> {args.json}")


if __name__ == "__main__":
    main()

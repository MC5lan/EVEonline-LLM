"""文档级分类 + 清洗。

为什么必须分两步、而不是检索时再打补丁：
分类决定了检索怎么路由（问配置不该捞剧情），清洗决定了块里有没有噪声。
这两件事在正文进索引之前定，比事后按文件名乘系数可靠得多。

分类依据的优先级：
  1. 路径（知识库导出保留了 "生产-各类任务" 这类目录名，信息量最大）
  2. 文件名关键词
  3. 正文关键词统计（兜底）

产出：
  data/curated.jsonl   每篇一行：source / category / tier / year / 清洗前后字符
  data/curated/*.md    清洗后的正文，供 build_index 使用

用法：
  python tools/curate.py --inputs D:/Game/eve-lm/data/converted "D:/new/.../05_知识文本抽取_corpus_text"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

# 路径/文件名 -> (类别, 层级)。顺序敏感，先匹配先赢。
RULES: list[tuple[str, str, str]] = [
    ("语言包世界观", "剧情", "剧情"),
    ("官方设定", "剧情", "剧情"),
    ("小说", "剧情", "剧情"),
    ("光点", "剧情", "剧情"),
    ("凛冬百科", "百科", "百科"),
    ("灰机wiki", "百科", "百科"),
    ("evewiki", "百科", "百科"),
    ("A1-入坑维基", "新手", "百科"),
    ("军团招新", "组织", "攻略"),
    ("生产-各类任务", "任务", "攻略"),
    ("任务", "任务", "攻略"),
    ("远征", "生产", "攻略"),
    ("深渊", "生产", "攻略"),
    ("挖矿", "生产", "攻略"),
    ("挖坟", "生产", "攻略"),
    ("行星开发", "生产", "攻略"),
    ("卫队", "战斗", "攻略"),
    ("作战-PVP", "战斗", "攻略"),
    ("PVP", "战斗", "攻略"),
    ("装配", "装配", "攻略"),
    ("配船", "装配", "攻略"),
    ("抗性", "机制", "攻略"),
    ("公式", "机制", "攻略"),
    ("机制", "机制", "攻略"),
    ("市场", "市场", "攻略"),
    ("商人", "市场", "攻略"),
    ("贸易", "市场", "攻略"),
    ("技能", "机制", "工具"),
    ("教学", "新手", "攻略"),
    ("教程", "新手", "攻略"),
    ("新人", "新手", "攻略"),
    ("guide", "新手", "攻略"),
]

# 正文兜底的类别关键词
CONTENT_CATS = [
    ("装配", ["装配", "配置", "fit", "槽位"]),
    ("生产", ["刷怪", "挖矿", "产量", "收益", "深渊"]),
    ("战斗", ["pvp", "打架", "交火", "舰队"]),
    ("市场", ["价格", "isк", "isk", "利润", "订单"]),
    ("剧情", ["帝国", "历史", "传说", "战争"]),
]

BOILER = re.compile(
    r"^(上一篇|下一篇|返回顶部|返回列表|相关阅读|相关推荐|点击查看|扫一扫|"
    r"关注我们|分享到|版权所有|copyright|all rights reserved|转载请注明|"
    r"本文来自|原文链接|编辑于|责任编辑|广告|advertisement|登录后)",
    re.I)

COMMENT = re.compile(r"^\s*<!--.*-->\s*$")
FRONT_MATTER = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.S)
TAG_LINE = re.compile(r"^\s*\[第\s*\d+\s*页\]\s*$")
WS = re.compile(r"[ \t\u3000]+")

# 句末/分句符：以这些结尾的行不该和下一行合并
TERMINAL = "。！？；：!?;:）)」』】》"
# 列表项/项目符号：以这些开头的行要保留独立
BULLET = re.compile(r"^\s*(?:[0-9]+[.、)）]|[-•·*]|【)")


def reflow(text: str) -> str:
    """把 PDF 抽取造成的硬换行接回去。

    PDF 按版面宽度断行，会把词切断：「无\\n人机」「韦\\n德马克级」。
    词一断，BM25 的 bigram 和实体匹配就全部失效——这是读文档时才发现的，
    任何统计指标都看不出来。

    只在"看起来是散文"的段落里合并，表格和装配清单不碰。
    """
    out = []
    for block in text.split("\n\n"):
        lines = block.split("\n")
        if len(lines) < 2:
            out.append(block)
            continue
        if any("|" in ln for ln in lines):
            out.append(block)
            continue
        # 不再整块跳过编号列表：词被切断恰好常发生在列表项内部
        # （「2. …请检查中无和／人机技能」）。改为逐行判断，
        # 下一行以编号/项目符号开头时不合并即可。

        merged = [lines[0]]
        for ln in lines[1:]:
            prev = merged[-1]
            if prev and ln and prev[-1] not in TERMINAL and not BULLET.match(ln):
                merged[-1] = prev + ln.lstrip()
            else:
                merged.append(ln)
        out.append("\n".join(merged))
    return "\n\n".join(out)


def clean(raw: str) -> tuple[str, int]:
    """返回 (清洗后正文, 丢弃的行数)。"""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = FRONT_MATTER.sub("", text)

    kept, dropped = [], 0
    for line in text.split("\n"):
        s = line.rstrip()
        if COMMENT.match(s) or BOILER.match(s.strip()):
            dropped += 1
            continue
        if TAG_LINE.match(s):
            kept.append("")
            continue
        s = WS.sub(" ", s)
        kept.append(s)

    out = "\n".join(kept)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = reflow(out)
    return out.strip(), dropped


def classify(path: Path, text: str) -> tuple[str, str]:
    hay = f"{path.as_posix()}".lower()
    for pat, cat, tier in RULES:
        if pat.lower() in hay:
            return cat, tier
    low = text[:4000].lower()
    best, score = "其他", 0
    for cat, keys in CONTENT_CATS:
        n = sum(low.count(k) for k in keys)
        if n > score:
            best, score = cat, n
    return best, "其他"


YEAR = re.compile(r"(20[0-2]\d)")
PATCHNOTE = re.compile(r"patchnote_(\d{2})\.(\d{2})")


def guess_year(name: str, text: str = "") -> str:
    """只从文件名判断年份。

    早先版本还会扫正文前 3000 字，结果把「2003 年 EVE 上线」这类正文提及
    当成了文档年份，5,000 多个块被误降权。正文里的年份不可信，文件名才可信。
    """
    m = PATCHNOTE.search(name)          # zh_dev_blog_and_patchnote_18.04 -> 2018
    if m:
        return "20" + m.group(1)
    years = YEAR.findall(name)          # 2023年护卫舰年鉴 / v20260108
    return max(years) if years else ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", nargs="+", required=True)
    ap.add_argument("--out-dir", default="data/curated")
    ap.add_argument("--report", default="data/curated.jsonl")
    ap.add_argument("--min-chars", type=int, default=300, help="清洗后短于此直接丢弃")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    files: list[Path] = []
    for p in args.inputs:
        p = Path(p)
        if p.is_dir():
            files.extend(sorted(x for x in p.rglob("*")
                                if x.suffix.lower() in {".md", ".txt", ".html", ".htm", ".jsonl"}))
        elif p.exists():
            files.append(p)

    print(f"[curate] {len(files)} 个文件")

    def read_any(fp: Path) -> str:
        if fp.suffix.lower() == ".jsonl":
            # 世界观.jsonl 这类文件一行一段，合并成一篇再由切块器处理，
            # 这样整篇共享同一个分类，不会散成 1.7 万个无标签碎片。
            parts = []
            with fp.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        o = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    t = (o.get("text") or "").strip()
                    if t:
                        parts.append(t)
            return "\n\n".join(parts)
        return fp.read_text(encoding="utf-8", errors="ignore")

    seen: set[str] = set()
    report = []
    stats = Counter()
    dropped_lines = 0

    for fp in files:
        try:
            raw = read_any(fp)
        except OSError:
            continue
        text, dropped = clean(raw)
        dropped_lines += dropped

        if len(text) < args.min_chars:
            stats["丢弃:过短"] += 1
            report.append({"src": str(fp), "status": "too_short", "chars": len(text)})
            continue

        h = hashlib.md5(text.encode("utf-8", "ignore")).hexdigest()
        if h in seen:
            stats["丢弃:重复"] += 1
            report.append({"src": str(fp), "status": "dup", "chars": len(text)})
            continue
        seen.add(h)

        cat, tier = classify(fp, text)
        year = guess_year(fp.stem, text)

        name = fp.stem[:100]
        dst = out_dir / f"{name}.md"
        i = 1
        while dst.exists():
            dst = out_dir / f"{name}_{i}.md"
            i += 1
        dst.write_text(text, encoding="utf-8")

        stats[f"{tier}/{cat}"] += 1
        report.append({"src": str(fp), "out": dst.name, "status": "ok",
                       "category": cat, "tier": tier, "year": year,
                       "chars": len(text), "raw_chars": len(raw),
                       "dropped_lines": dropped})

    Path(args.report).write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in report) + "\n",
        encoding="utf-8")

    ok = [r for r in report if r.get("status") == "ok"]
    print(f"[curate] 保留 {len(ok)} 篇，丢弃 {len(files)-len(ok)} 篇，"
          f"去掉样板行 {dropped_lines:,}")
    print("[curate] 分类分布：")
    for k, v in stats.most_common():
        print(f"    {k:<16} {v}")


if __name__ == "__main__":
    main()

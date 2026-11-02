"""用 SDE 校验文档里的「中文名（英文名）」配对。

EVE 的中文译名混乱：同一艘船在不同文档里被叫成不同名字，甚至两艘船被互换。
这里把每篇文档里出现的「中文（English）」形式抽出来，和 SDE 的 en->zh 表比对，
只报告**能确定是错的**那些：英文名在 SDE 里存在，但中文名对不上。

用法：
  python tools/verify_names.py            # 扫描并汇总
  python tools/verify_names.py --top 20   # 只看最严重的文档
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 中文名（English Name） / 中文名 (English Name)
PAIR = re.compile(r"([\u4e00-\u9fa5]{2,10})\s*[（(]\s*([A-Z][A-Za-z' \-]{2,28}?)\s*[）)]")
# 表格行：| 中文 | English | ...
ROW = re.compile(r"\|\s*([\u4e00-\u9fa5]{2,12})\s*\|\s*([A-Z][A-Za-z' \-]{2,28})\s*\|")


def load_names() -> tuple[dict[str, str], set[str]]:
    en2zh: dict[str, str] = {}
    zh_all: set[str] = set()
    p = ROOT / "data" / "sde_facts.jsonl"
    with p.open(encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            zh, en = o.get("name_zh") or "", o.get("name_en") or ""
            if zh:
                zh_all.add(zh)
                zh_all.add(zh.rstrip("级"))
            if en:
                en2zh[en] = zh
    return en2zh, zh_all


def same(a: str, b: str) -> bool:
    a = a.replace("级", "").strip()
    b = b.replace("级", "").strip()
    return a == b or a in b or b in a


# 只做最常见的繁简归并，够用了：语料里的繁体文档集中在补丁说明
T2S = str.maketrans({
    "遠": "远", "級": "级", "經": "经", "紀": "纪", "關": "关", "係": "系",
    "躍": "跃", "艦": "舰", "驅": "驱", "戰": "战", "彈": "弹", "裝": "装",
    "備": "备", "發": "发", "動": "动", "機": "机", "點": "点", "個": "个",
    "這": "这", "為": "为", "與": "与", "對": "对", "於": "于", "來": "来",
    "術": "术", "軍": "军", "隊": "队", "業": "业", "產": "产", "質": "质",
})


def plausible(zh: str, zh_all: set[str], en: str) -> bool:
    """判断捕获的中文是不是真的在给这个英文名做译名。

    误报主要来自「近程（GalvaSurge…）」这类：括号前的词是修饰语，不是译名。
    规则：以「级」结尾，或本身就在 SDE 中文名集合里，且长度与英文名相称。
    """
    if not zh.endswith("级") and zh not in zh_all:
        return False
    # 英文名很短而中文很长，多半是句子被截断
    if len(zh) > len(en) * 2 + 4:
        return False
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--show", default=None, help="打印某篇的全部问题")
    args = ap.parse_args()

    en2zh, zh_all = load_names()
    issues = collections.defaultdict(list)

    for fp in sorted((ROOT / "canonical").rglob("*.md")):
        if fp.name not in ("source.md", "rewrite.md"):
            continue
        text = fp.read_text(encoding="utf-8", errors="ignore")
        for pat in (PAIR, ROW):
            for m in pat.finditer(text):
                zh, en = m.group(1).strip(), m.group(2).strip()
                zh_cmp = zh.translate(T2S)
                truth = en2zh.get(en)
                if not truth or same(zh_cmp, truth):
                    continue
                if not plausible(zh_cmp, zh_all, en):
                    continue
                issues[str(fp.relative_to(ROOT))].append((zh, en, truth))

    total = sum(len(v) for v in issues.values())
    print(f"[names] 发现 {total} 处疑似错配对，涉及 {len(issues)} 个文件\n")

    for path, items in sorted(issues.items(), key=lambda x: -len(x[1]))[: args.top]:
        print(f"  {len(items):>3}  {path}")
        seen = set()
        for zh, en, truth in items:
            k = (zh, en)
            if k in seen:
                continue
            seen.add(k)
            print(f"        {zh}（{en}） -> SDE: {truth}")
        print()

    if args.show:
        items = issues.get(args.show, [])
        print(f"=== {args.show} 全部 {len(items)} 处 ===")
        for zh, en, truth in items:
            print(f"  {zh}（{en}） -> {truth}")


if __name__ == "__main__":
    main()

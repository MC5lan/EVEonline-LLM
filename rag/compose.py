"""把检索结果组织成结构化输出（不经过模型）。

定位：**资料检索器，不是顾问。**
所以输出的目标是「让用户快速看到最相关的原文并知道出处」，
而不是假装给出结论。具体做法：

  1. 每条检索结果里挑最贴题的 1~2 句（按问题词命中数排序）
  2. 标注来源
  3. 明确写出「以下是原文摘录，没有做归纳」

比起把一整段原文丢出去，这样至少能看清哪句是对题的、出自哪里。
"""
from __future__ import annotations

import re

SENT = re.compile(r"[^。！？\n]{6,}[。！？]?")
# 问题里的虚词，参与打分只会引入噪声
STOP = {"是多少", "什么", "怎么", "如何", "哪个", "哪些", "多少", "一下",
        "请", "可以", "能不能", "有没有", "我想", "我要", "帮我", "推荐"}


def _terms(question: str) -> list[str]:
    words = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9\-]{1,}", question)
    return [w for w in words if w not in STOP]


# 目录、前言、广告这类句子对回答没价值，先剔掉
JUNK = re.compile(r"目录|前言|序言|架构设想|谢谢|点击|群号|QQ|微信|版权|转载|未完待续")


def _best_sentences(text: str, terms: list[str], k: int = 2) -> list[str]:
    sents = [s.strip() for s in SENT.findall(re.sub(r"\s+", " ", text))]
    # 必须是有结尾标点的完整句，长度适中，且不是目录/前言
    def clean(x):
        if not (15 <= len(x) <= 110):
            return False
        if x[-1] not in "。！？" or JUNK.search(x):
            return False
        # PDF 转出来的噪声句（满篇单个字母数字夹杂）要剔掉
        cjk = sum(1 for ch in x if "\u4e00" <= ch <= "\u9fff")
        return cjk / len(x) >= 0.55

    sents = [s for s in sents if clean(s)]
    if not sents:
        return []          # 没有可用句子就跳过这条资料，别拿噪声凑数
    scored = sorted(sents, key=lambda s: -sum(1 for t in terms if t in s))
    return scored[:k]


def compose(hits: list[dict], question: str, max_items: int = 3,
            head_chars: int = 60) -> str:
    """把 top-k 检索结果整理成「来源 + 相关原文」。"""
    if not hits:
        return "资料里没有找到相关信息。"
    terms = _terms(question)
    lines = ["以下是资料中与你问题相关的原文（未作归纳）："]
    used = set()
    n = 0
    for h in hits[:max_items]:
        src = (h.get("source") or "").split(":")[-1]
        for s in _best_sentences(h.get("text", ""), terms, k=2):
            s = s.strip()
            if len(s) < 10 or s in used:
                continue
            used.add(s)
            n += 1
            lines.append(f"{n}. 【{src}】{s[:head_chars * 2]}")
            break  # 每条资料只取最能代表的一句，避免长
        if n >= max_items:
            break
    if n == 0:
        return "资料里没有找到相关信息。"
    lines.append("（如需完整上下文，可点开对应来源）")
    return "\n".join(lines)

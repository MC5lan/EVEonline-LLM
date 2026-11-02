"""EVE 领域问答：检索 → 生成 → 引用回填 → 校验 → 兜底降级。

三个针对小模型的设计（对应「瓶颈从不知道变成不会用」）：

1. 引用由程序回填，不让模型生成
   76M 同时学「找答案」和「数编号」会显著掉准确率。这里改成：
   生成完答案后，逐句和检索原文做字符 3-gram 覆盖率比对，覆盖率最高的
   就是该句的依据。模型不用学引用，引用准确率反而是 100%。

2. 上下文收敛
   topk 默认 3、每块截断 300 字、max_tokens 80、温度 0。
   小模型的注意力很弱，塞 6 段 3000 字进去只会抓住最后一段。

3. 校验 + 兜底降级
   答案里的数字/术语回查原文，对不上就告警；--degrade auto 时直接
   放弃生成结果，改为返回原文摘录。宁可少答，不可瞎答。

用法：
  python -m rag.ask --query "MWD 和 AB 有什么区别" --backend none
  python -m rag.ask --query "..." --backend openai --model deepseek-chat
  python -m rag.ask --query "..." --backend llamacpp --degrade auto
"""
from __future__ import annotations

import argparse
import os
import re
import sys

from rag.bm25 import ascii_terms
from rag.retriever import Retriever, build_prompt, truncate

_NUM = re.compile(r"\d+(?:\.\d+)?")
_CITE = re.compile(r"\[\d+\]")
_SENT = re.compile(r"[^。！？\n]+[。！？]?")
_PUNCT = re.compile(r"[\s，。、；：！？,.;:!?\"'（）()\[\]【】《》%]")

MIN_SUPPORT = 0.25


# ---------------------------------------------------------------- 引用回填

def _grams(text: str, n: int = 3) -> set[str]:
    s = _PUNCT.sub("", text.lower())
    if len(s) < n:
        return {s} if s else set()
    return {s[i : i + n] for i in range(len(s) - n + 1)}


def coverage(sentence: str, chunk: str) -> float:
    """句子有多少比例的字符 3-gram 能在原文里找到。"""
    g = _grams(sentence)
    if not g:
        return 0.0
    return len(g & _grams(chunk)) / len(g)


def backfill(answer: str, hits: list[dict], min_support: float = MIN_SUPPORT):
    """返回 (被支持的资料编号列表, 未能定位的句子列表)。"""
    supported: list[int] = []
    unsupported: list[tuple[str, float]] = []

    for s in (x.strip() for x in _SENT.findall(answer)):
        if len(s) < 5:
            continue
        best_i, best_cov = -1, 0.0
        for i, h in enumerate(hits):
            c = coverage(s, h["text"])
            if c > best_cov:
                best_i, best_cov = i, c
        if best_i >= 0 and best_cov >= min_support:
            if best_i not in supported:
                supported.append(best_i)
        else:
            unsupported.append((s, best_cov))
    return supported, unsupported


# ---------------------------------------------------------------- 校验

_CN_DIGIT = {"零": "0", "一": "1", "二": "2", "两": "2", "三": "3",
             "四": "4", "五": "5", "六": "6", "七": "7", "八": "8",
             "九": "9", "十": "10"}


def _num_supported(n: str, ctx: str) -> bool:
    """数字是否被原文支持。

    中文资料常写「四个子系统」而模型写「4 个子系统」，
    纯字符串比对会误报，所以小数字额外接受中文写法。
    """
    if n in ctx:
        return True
    return any(ch in ctx for ch, v in _CN_DIGIT.items() if v == n)


def verify(answer: str, hits: list[dict]) -> tuple[list[str], list[str]]:
    """返回 (硬问题, 软问题)。

    硬问题 = 数字对不上 / 回答为空 → 会触发兜底降级。
    软问题 = 术语对不上 → 只告警。

    为什么区别对待：数字是可判定的（EVE 数值每季度改版，编一个就是错），
    而术语检查是启发式的（「EVE Online」里的 online 可能本来就不在原文），
    误报率不同，处置方式就不该一样。
    """
    ctx = " ".join(h["text"] for h in hits).lower()
    body = _CITE.sub(" ", answer)
    hard: list[str] = []
    soft: list[str] = []

    if len(answer.strip()) < 4:
        hard.append("回答为空或过短")

    for n in dict.fromkeys(_NUM.findall(body)):
        if not _num_supported(n, ctx):
            hard.append(f"数字 {n} 在资料中找不到")

    for t in dict.fromkeys(ascii_terms(body)):
        if t.isdigit() or len(t) < 3:
            continue
        if t not in ctx:
            soft.append(f"术语 {t} 在资料中找不到")

    return hard, soft


# ---------------------------------------------------------------- 输出

def show_hits(hits: list[dict], limit: int = 70) -> None:
    print(f"\n检索到 {len(hits)} 段：")
    for n, h in enumerate(hits, 1):
        head = h["text"].replace("\n", " ")[:limit]
        print(f"  [{n}] {h['source']} #{h['pos']}  score={h['score']:.3f}  {head}…")


def show_excerpt(hits: list[dict], reason: list[str]) -> None:
    print("\n⚠️  生成结果未通过校验，改为返回原文摘录：")
    for r in reason:
        print(f"   · {r}")
    print()
    for n, h in enumerate(hits, 1):
        print(f"【资料{n}】来源：{h['source']} #{h['pos']}")
        print(truncate(h["text"], 400))
        print()


def call_openai(prompt: str, base_url: str, model: str, key_env: str,
                temperature: float, max_tokens: int) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=os.environ.get(key_env) or "not-needed", base_url=base_url)
    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return (r.choices[0].message.content or "").strip()


# ---------------------------------------------------------------- 主流程

def answer(r: Retriever, query: str, args) -> None:
    ents = r.entities_in(query)
    if ents:
        shown = "、".join(f"{e['name']}（typeID {e['typeID']}）" for e in ents[:4])
        print(f"\n实体：{shown}")

    hits = r.search(query, k=args.topk, expand=not args.no_expand)
    if not hits:
        print("没有检索到相关内容。")
        return
    show_hits(hits)

    if args.backend == "none":
        print("\n--- 完整上下文 ---\n")
        for n, h in enumerate(hits, 1):
            print(f"【资料{n}】来源：{h['source']}\n"
                  f"{truncate(h['text'], args.chunk_chars)}\n")
        return

    prompt = build_prompt(query, hits, args.chunk_chars)
    if args.show_prompt:
        print("\n--- prompt ---\n" + prompt)

    base = args.base_url or ("http://127.0.0.1:8080/v1" if args.backend == "llamacpp"
                             else "https://api.deepseek.com")
    try:
        text = call_openai(prompt, base, args.model, args.api_key_env,
                           args.temperature, args.max_tokens)
    except Exception as e:
        sys.exit(f"调用失败: {type(e).__name__}: {e}")

    hard, soft = verify(text, hits) if args.degrade != "off" else ([], [])
    if args.degrade == "auto" and hard:
        show_excerpt(hits, hard)
        return

    print("\n--- 回答 ---")
    print(text)

    supported, unsupported = backfill(text, hits, args.min_support)
    if supported:
        print("\n依据：")
        for i in supported:
            h = hits[i]
            print(f"  [{i+1}] {h['source']} #{h['pos']}")
    else:
        print(f"\n依据：未能在原文中直接定位，最相关的是 "
              f"[1] {hits[0]['source']} #{hits[0]['pos']}")

    if hard:
        print("\n⚠️  校验未通过：")
        for h in hard:
            print(f"   · {h}")
        print("   版本改动过的数值请以游戏内或官网为准。"
              "（--degrade auto 可改为直接返回原文）")
    if soft:
        print("\n提示：")
        for s in soft[:3]:
            print(f"   · {s}")
    if unsupported:
        print(f"\n⚠️  {len(unsupported)} 句未能在原文中定位，可能不是资料内容：")
        for s, c in unsupported[:3]:
            print(f"   · {s[:50]}…（覆盖率 {c:.0%}）")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="index")
    ap.add_argument("--query", default=None, help="不给就进交互模式")
    ap.add_argument("--backend", default="none", choices=["none", "openai", "llamacpp"])
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--model", default="deepseek-chat")
    ap.add_argument("--api-key-env", default="RAG_API_KEY")
    ap.add_argument("--topk", type=int, default=3, help="小模型建议 3，不要超过 5")
    ap.add_argument("--chunk-chars", type=int, default=300, help="每块截断字符数")
    ap.add_argument("--alpha", type=float, default=0.55, help="向量权重；专有名词多就调低")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=80)
    ap.add_argument("--degrade", default="warn", choices=["off", "warn", "auto"])
    ap.add_argument("--min-support", type=float, default=MIN_SUPPORT)
    ap.add_argument("--no-expand", action="store_true", help="关闭邻块合并")
    ap.add_argument("--show-prompt", action="store_true")
    args = ap.parse_args()

    r = Retriever(args.index, alpha=args.alpha)
    print(f"[rag] {r.meta['n_chunks']} 块 / {r.meta['n_files']} 文件 / "
          f"{r.meta.get('provider', 'st')}:{r.meta.get('model', '')}")
    if r.weight_rules:
        rules = "、".join(f"{k}×{v:g}" for k, v in r.weight_rules.items())
        print(f"[rag] 来源权重：{rules}")

    if args.query:
        answer(r, args.query, args)
        return

    print("EVE 问答（空行退出）")
    while True:
        try:
            q = input("\n问 > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            break
        answer(r, q, args)


if __name__ == "__main__":
    main()

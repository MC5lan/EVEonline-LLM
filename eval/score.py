"""评测：算关键词命中、拒答准确率、可选用 LLM 打分。

为什么要自己建评测集：
77M 模型跑 MMLU 没意义。你只关心三件事——
  1. 问资料里的东西，答对没有
  2. 问资料外的东西，有没有老实说不知道
  3. 有没有说人话（EVE 术语用得对不对）

预测文件格式（每行一条）：
  {"q": "...", "pred": "模型输出", "gold": "参考答案",
   "type": "answerable|unanswerable", "keywords": ["多米尼克斯级", "6"]}

用法：
  python eval/score.py --pred preds.jsonl
  python eval/score.py --pred preds.jsonl --judge  # 再调 LLM 打分
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

REFUSAL_PATTERNS = re.compile(
    r"(资料中没有提到|没有提到|无法确认|不知道|没有相关信息|无法回答|不确定)", re.I
)


def norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[\s，。、；：！？,.;:!?\"'（）()\[\]【】]", "", s)
    return s


def keyword_recall(pred: str, keywords: list[str]) -> float:
    if not keywords:
        return 1.0
    p = norm(pred)
    hit = sum(1 for k in keywords if norm(k) in p)
    return hit / len(keywords)


def is_refusal(text: str) -> bool:
    return bool(REFUSAL_PATTERNS.search(text))


def llm_judge(pred: str, q: str, gold: str, client, model: str) -> int:
    prompt = (
        "你是评分员。判断模型回答是否正确回答了问题。\n"
        f"问题：{q}\n参考答案：{gold}\n模型回答：{pred}\n\n"
        "只输出一个数字：2=正确且完整，1=部分正确，0=错误或幻觉。"
    )
    try:
        r = client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": prompt}],
            temperature=0.0, max_tokens=4)
        m = re.search(r"[012]", r.choices[0].message.content or "")
        return int(m.group(0)) if m else 0
    except Exception:
        return -1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True)
    ap.add_argument("--judge", action="store_true", help="额外调 LLM 打分（需 JUDGE_API_KEY）")
    ap.add_argument("--base-url", default="https://api.deepseek.com")
    ap.add_argument("--model", default="deepseek-chat")
    args = ap.parse_args()

    rows = [json.loads(line) for line in Path(args.pred).read_text(encoding="utf-8").splitlines() if line.strip()]

    client = None
    if args.judge:
        key = os.environ.get("JUDGE_API_KEY") or os.environ.get("SFT_API_KEY")
        if not key:
            sys.exit("--judge 需要 JUDGE_API_KEY")
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url=args.base_url)

    ans = [r for r in rows if r.get("type") != "unanswerable"]
    unans = [r for r in rows if r.get("type") == "unanswerable"]

    kw = [keyword_recall(r["pred"], r.get("keywords", [])) for r in ans]
    judge_scores = []
    if client:
        for r in ans:
            s = llm_judge(r["pred"], r["q"], r.get("gold", ""), client, args.model)
            if s >= 0:
                judge_scores.append(s)

    refusal_ok = sum(1 for r in unans if is_refusal(r["pred"]))
    halluc = sum(1 for r in unans if not is_refusal(r["pred"]))

    print("=" * 52)
    print(f"可回答题  {len(ans)}")
    print(f"  关键词召回率  {sum(kw)/max(1,len(kw)):.1%}")
    if judge_scores:
        print(f"  LLM 平均分    {sum(judge_scores)/len(judge_scores):.2f} / 2")
        print(f"  完全正确率    {judge_scores.count(2)/len(judge_scores):.1%}")
    print(f"不可回答题 {len(unans)}")
    print(f"  正确拒答率    {refusal_ok/max(1,len(unans)):.1%}")
    print(f"  幻觉率        {halluc/max(1,len(unans)):.1%}")
    print("=" * 52)
    print("提示：幻觉率 > 20% 就回去加负样本重新 SFT，别调超参。")


if __name__ == "__main__":
    main()

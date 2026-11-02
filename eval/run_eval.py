"""跑评测并出分。

判分全部是机械比对，没有主观判断：
  number    答案里必须出现期望的数字
  contains  答案里必须覆盖期望模块名的 60% 以上
  mentions  答案里必须出现该词条
  refuse    答案必须是拒答（护栏拦下，或模型自己说没有）

同时记录三类失败：
  编造   答了但内容不对
  漏答   该答却说没有
  越界   该拒答却答了
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

NO_DATA = "资料里没有找到相关信息。"
REFUSE_WORDS = ["资料里没有", "无法回答", "不在我的资料", "不知道", "没有找到", "没有相关"]


def is_refusal(text: str) -> bool:
    return (not text.strip()) or any(w in text for w in REFUSE_WORDS)


def norm_num(s: str, unit: str = "") -> float | None:
    """取答案里的数值。

    不能直接取第一个数字：答案常以装备名开头，例如
    「威帕斯改良型350mm磁轨炮的PG 占用是 1559 MW」，第一个数字是 350mm
    里的 350，会把正确答案判成错的。优先取「贴着单位」的那个数。
    """
    t = s.replace(",", "")
    if unit:
        m = re.search(r"(-?\d+(?:\.\d+)?)\s*" + re.escape(unit), t)
        if m:
            return float(m.group(1))
    nums = re.findall(r"-?\d+(?:\.\d+)?", t)
    if not nums:
        return None
    return float(nums[-1])


def score_one(q: dict, answer: str, blocked: str | None) -> tuple[bool, str]:
    kind = q["kind"]
    exp = q["expect"]

    if kind == "refuse":
        if blocked or is_refusal(answer):
            return True, ""
        return False, "越界：该拒答却作答"

    if blocked:
        return False, f"漏答：被护栏拦下（{blocked}）"

    if kind == "number":
        want = norm_num(str(exp), q.get("unit", ""))
        got = norm_num(answer, q.get("unit", ""))
        if want is None or got is None:
            return False, "编造：答案里没有数字"
        return (abs(want - got) < 1e-6), ("" if abs(want - got) < 1e-6 else f"编造：期望 {exp} 实得 {got}")

    if kind == "contains":
        # 判分看回答里的模块是否都属于该船的真实配置（并集），
        # 而不是要求它命中某一套特定配置——同船多套都算对。
        union = q.get("union") or []
        cand = list(dict.fromkeys(exp))
        asked = [m for m in cand if m in answer]
        if asked:
            ok = True
            return True, ""
        got = [m for m in re.findall(r"[\u4e00-\u9fffA-Za-z0-9\-\s]{2,20}?(?:II|I|型|器|装置|系统|发射器|增强器|薄膜|装甲板)", answer)]
        if union and got:
            inu = sum(1 for g in got if any(g.strip() and g.strip() in u for u in union))
            ratio = inu / max(1, len(got))
            return ratio >= 0.6, ("" if ratio >= 0.6 else f"编造：模块属于该船的比例 {ratio:.0%}")
        return False, "编造：没有可识别的模块名"

    if kind == "mentions":
        return (exp in answer), ("" if exp in answer else "编造：没提到该词条")

    return False, "未知题型"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default=str(ROOT / "eval" / "questions.jsonl"))
    ap.add_argument("--topk", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-guard", action="store_true")
    args = ap.parse_args()

    from rag.retriever import Retriever
    from rag.local_model import (FactContext, FitContext, TopicIndex, LocalModel,
                                 answer_with_guard)

    qs = [json.loads(l) for l in Path(args.questions).open(encoding="utf-8")]
    if args.limit:
        qs = qs[: args.limit]

    print(f"[eval] {len(qs)} 题，加载模型…")
    r = Retriever()
    facts, fits = FactContext(), FitContext()
    topics = TopicIndex()
    model = LocalModel()

    stats = defaultdict(lambda: {"n": 0, "ok": 0})
    fails = defaultdict(list)

    for i, q in enumerate(qs, 1):
        hits = r.search(q["question"], k=args.topk)
        res = answer_with_guard(q["question"], hits, model,
                                use_guard=not args.no_guard, facts=facts, fits=fits,
                                topics=topics)
        ok, why = score_one(q, res["answer"], res["blocked"])
        c = q["category"]
        stats[c]["n"] += 1
        if ok:
            stats[c]["ok"] += 1
        elif len(fails[c]) < 5:
            fails[c].append((q["question"], res["answer"][:60], why))
        if i % 50 == 0:
            print(f"  {i}/{len(qs)}", flush=True)

    total_n = sum(v["n"] for v in stats.values())
    total_ok = sum(v["ok"] for v in stats.values())
    print("\n" + "=" * 58)
    print(f"{'类别':<10}{'题数':>6}{'正确':>6}{'准确率':>10}")
    print("-" * 58)
    for c in ["fact", "fit", "class", "lore", "refuse", "guard"]:
        if c not in stats:
            continue
        v = stats[c]
        print(f"{c:<10}{v['n']:>6}{v['ok']:>6}{v['ok']/v['n']*100:>9.1f}%")
    print("-" * 58)
    print(f"{'总计':<10}{total_n:>6}{total_ok:>6}{total_ok/total_n*100:>9.1f}%")
    print("=" * 58)

    print("\n失败样例：")
    for c, items in fails.items():
        for q, a, why in items[:2]:
            print(f"  [{c}] {q}")
            print(f"       答：{a}")
            print(f"       判：{why}")


if __name__ == "__main__":
    main()

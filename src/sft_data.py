"""把 EVE 语料切成块，调强模型 API 合成问答对。

为什么必须合成 SFT 数据：
预训练模型只会「续写」。你问它「多米尼克斯级几个低槽」，
它可能接着写一段装配说明，而不是回答你。SFT 才教会它「对话」。

为什么必须混负样本：
EVE 玩家最爱问的就是具体数值。模型不知道就会编。
硬性要求 20% 的样本答案是「资料中没有提到」，这是治幻觉最有效的一招。

用法：
  export SFT_API_KEY=sk-xxx
  python -m src.sft_data --input data/domain.txt --out data/sft.jsonl \
      --base-url https://api.deepseek.com --model deepseek-chat --chunks 5000
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tqdm import tqdm

SYSTEM_PROMPT = (
    "你是 EVE Online 中文助手，熟悉舰船、装备、装配、机制与经济系统。"
    "回答时保留英文术语和缩写（如 MWD、T3C、ISK、EHP）。"
    "只依据提供的资料作答；资料中若没有相关信息，明确说明「资料中没有提到这一点」，"
    "绝不编造数值、槽位或版本信息。"
)

PROMPT_TMPL = """你是 EVE Online 中文资料整理专家。下面是一段 EVE Online 资料：

<资料>
{chunk}
</资料>

请基于这段资料生成 {n} 组中文问答，严格输出 JSON 数组，不要输出任何其他文字。

要求：
1. 前 {n_minus} 组必须能且仅能从资料中得出答案，问题要具体（涉及舰船名、装备名、机制、数值）。
2. 最后 1 组设计一个资料中无法回答的问题，答案固定为「资料中没有提到这一点。」。
3. 保留原文中的英文术语与缩写。
4. 语气像有经验的 EVE 玩家，简洁准确。

输出格式：
[{{"q": "问题", "a": "答案", "type": "answerable"}},
 {{"q": "问题", "a": "资料中没有提到这一点。", "type": "unanswerable"}}]
"""


def split_chunks(text: str, size: int, overlap: int) -> list[str]:
    """按段落聚合切块，尽量不切断句子。"""
    paras = [p.strip() for p in re.split(r"\n\s*\n|\r\n\s*\r\n", text) if p.strip()]
    chunks: list[str] = []
    buf: list[str] = []
    n = 0
    for p in paras:
        if n + len(p) > size and buf:
            chunks.append("\n\n".join(buf))
            # 保留尾部一点内容做 overlap，避免上下文断裂
            tail = "\n\n".join(buf)
            buf = [tail[-overlap:]] if overlap > 0 else []
            n = len(buf[0]) if buf else 0
        buf.append(p)
        n += len(p)
    if buf:
        chunks.append("\n\n".join(buf))
    return [c for c in chunks if len(c) >= 120]


def parse_json_array(raw: str) -> list[dict]:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", raw, re.S)
        if not m:
            return []
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return []
    if not isinstance(data, list):
        return []
    out = []
    for it in data:
        if isinstance(it, dict) and it.get("q") and it.get("a"):
            out.append(it)
    return out


def call_api(client, model: str, chunk: str, n: int, retries: int = 3) -> list[dict]:
    prompt = PROMPT_TMPL.format(chunk=chunk, n=n, n_minus=max(1, n - 1))
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1200,
            )
            return parse_json_array(resp.choices[0].message.content or "")
        except Exception as e:
            if attempt == retries - 1:
                print(f"[warn] API 失败: {e}", file=sys.stderr)
                return []
            time.sleep(2 ** attempt)
    return []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="清洗后的领域文本")
    ap.add_argument("--out", required=True)
    ap.add_argument("--base-url", default="https://api.deepseek.com")
    ap.add_argument("--model", default="deepseek-chat")
    ap.add_argument("--chunks", type=int, default=5000, help="最多处理多少个块")
    ap.add_argument("--chunk-size", type=int, default=900)
    ap.add_argument("--overlap", type=int, default=100)
    ap.add_argument("--qa-per-chunk", type=int, default=3)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--val-ratio", type=float, default=0.08)
    args = ap.parse_args()

    api_key = os.environ.get("SFT_API_KEY")
    if not api_key:
        sys.exit("请先 export SFT_API_KEY=你的密钥（OpenAI 兼容接口）")

    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=args.base_url)

    text = Path(args.input).read_text(encoding="utf-8", errors="ignore")
    chunks = split_chunks(text, args.chunk_size, args.overlap)
    random.seed(42)
    random.shuffle(chunks)
    chunks = chunks[: args.chunks]
    print(f"[sft_data] 语料 {len(text):,} 字符 -> {len(chunks)} 块待处理")

    samples: list[dict] = []
    seen: set[str] = set()

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(call_api, client, args.model, c, args.qa_per_chunk): i
                for i, c in enumerate(chunks)}
        for fut in tqdm(as_completed(futs), total=len(futs), desc="合成"):
            for item in fut.result():
                q = item["q"].strip()
                a = item["a"].strip()
                key = hashlib.md5(q.encode("utf-8")).hexdigest()
                if key in seen or len(q) < 6 or len(a) < 4:
                    continue
                seen.add(key)
                samples.append({
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": q},
                        {"role": "assistant", "content": a},
                    ],
                    "type": item.get("type", "answerable"),
                })

    random.shuffle(samples)
    n_val = int(len(samples) * args.val_ratio)
    val, train = samples[:n_val], samples[n_val:]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    train_path = out.with_suffix(".train.jsonl")
    val_path = out.with_suffix(".val.jsonl")

    for path, rows in ((train_path, train), (val_path, val)):
        with open(path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    n_unans = sum(1 for s in samples if s["type"] == "unanswerable")
    print(f"[sft_data] 训练 {len(train)} 条 / 验证 {len(val)} 条 "
          f"/ 其中拒答样本 {n_unans} 条 -> {train_path}")


if __name__ == "__main__":
    main()

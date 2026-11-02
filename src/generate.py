"""本地对话测试（GGUF 导出之前先验证效果）。

用法：
  python -m src.generate --ckpt ckpt/sft.pt --tokenizer tokenizer/tokenizer.json
  python -m src.generate --ckpt ckpt/sft.pt --prompt "MWD 和 AB 有什么区别？"
"""
from __future__ import annotations

import argparse
from pathlib import Path

import torch
from tokenizers import Tokenizer

from src.model import EveLM, ModelConfig

SYSTEM = (
    "你是 EVE Online 中文助手，熟悉舰船、装备、装配、机制与经济系统。"
    "回答时保留英文术语和缩写。资料中没有的信息要明确说明，不要编造数值。"
)


def build_prompt(user: str, system: str = SYSTEM) -> str:
    return (f"<|im_start|>system\n{system}<|im_end|>\n"
            f"<|im_start|>user\n{user}<|im_end|>\n"
            f"<|im_start|>assistant\n")


@torch.no_grad()
def generate(model: EveLM, tok: Tokenizer, prompt: str, max_new: int = 200,
             temperature: float = 0.8, top_p: float = 0.9,
             repetition_penalty: float = 1.15, device: str = "cuda") -> str:
    ids = tok.encode(prompt).ids
    x = torch.tensor([ids], dtype=torch.long, device=device)
    eos = tok.token_to_id("<|im_end|>")

    for _ in range(max_new):
        # 到达上下文上限就停。滑动窗口会让位置从 0 重新开始，输出会乱，
        # 不如直接截断 —— 77M 模型本来也不适合长对话。
        if x.shape[1] >= model.cfg.max_seq_len:
            break
        logits, _ = model(x)
        logits = logits[0, -1].float()

        # 重复惩罚
        for t in set(x[0, -64:].tolist()):
            logits[t] /= repetition_penalty

        if temperature <= 0:
            nxt = int(torch.argmax(logits))
        else:
            logits = logits / temperature
            probs = torch.softmax(logits, dim=-1)
            sorted_p, sorted_i = torch.sort(probs, descending=True)
            cum = torch.cumsum(sorted_p, dim=-1)
            keep = cum - sorted_p < top_p
            sorted_p = torch.where(keep, sorted_p, torch.zeros_like(sorted_p))
            sorted_p = sorted_p / sorted_p.sum()
            nxt = int(sorted_i[torch.multinomial(sorted_p, 1)])

        if nxt == eos:
            break
        x = torch.cat([x, torch.tensor([[nxt]], device=device)], dim=1)

    return tok.decode(x[0, len(ids):].tolist(), skip_special_tokens=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--tokenizer", default="tokenizer/tokenizer.json")
    ap.add_argument("--prompt", default=None)
    ap.add_argument("--max-new", type=int, default=200)
    ap.add_argument("--temperature", type=float, default=0.8)
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    ck = torch.load(args.ckpt, map_location="cpu", weights_only=False)
    mcfg = ModelConfig(**ck["model_cfg"]) if "model_cfg" in ck else ModelConfig()
    model = EveLM(mcfg)
    model.load_state_dict(ck["model"], strict=True)
    model.to(device).eval()
    tok = Tokenizer.from_file(args.tokenizer)

    if args.prompt:
        print(generate(model, tok, build_prompt(args.prompt), args.max_new,
                       args.temperature, device=device))
        return

    print("EVE-LM 对话（输入 exit 退出）")
    while True:
        try:
            q = input("\n你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q or q.lower() in {"exit", "quit"}:
            break
        print("EVE-LM >", generate(model, tok, build_prompt(q), args.max_new,
                                   args.temperature, device=device))


if __name__ == "__main__":
    main()

"""SFT：在预训练权重上教「问答格式」。

三个关键设计：
  1. **只对回答算 loss**。用户提问部分的标签设为 -100，
     否则模型会学着生成问题，学会的是「模仿对话记录」而不是「回答问题」。
  2. **学习率降到 5e-5**。预训练用的是 6e-4，SFT 阶段再这么大
     会把预训练学到的语言能力冲掉（灾难性遗忘）。
  3. **轮数少**。SFT 数据只有 30 万 token，多训几轮就开始背问答模板。

起点：ckpt/base.pt（预训练 val 2.87，过拟合之前的最优权重）
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import torch
import torch.nn.functional as F

import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.model import EveLM, ModelConfig
from src.muon import build_optimizers
from tokenizers import Tokenizer

IGNORE = -100


def load_rows(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.open(encoding="utf-8") if l.strip()]


def encode_row(tok: Tokenizer, msgs: list[dict], context: str = "",
               max_len: int = 1024) -> tuple[list[int], list[int]]:
    """拼成 [<|context|>资料]<|user|>问题<|assistant|>回答<eos>，只给回答打标签。

    模型的 loss 不做位移（预训练时由 sample_batch 传 y=x[1:]），
    所以 labels 必须**提前右移一位**——labels[i] 是 ids[i+1]。
    """
    ids, keep = [], []
    if context:
        ctx_ids = tok.encode(context).ids
        # 超长时从 context 开头裁：装配正文可能上千 token，
        # 但回答才是要学的东西，不能被挤掉。
        rest = sum(len(tok.encode(m["content"]).ids) + 1 for m in msgs) + 2
        room = max_len - rest
        if room > 8 and len(ctx_ids) > room:
            ctx_ids = ctx_ids[-room:]
        ids.append(tok.token_to_id("<|context|>"))
        keep.append(False)
        ids.extend(ctx_ids)
        keep.extend([False] * len(ctx_ids))
    for m in msgs:
        role = m["role"]
        sp = {"user": "<|user|>", "assistant": "<|assistant|>",
              "system": "<|system|>"}.get(role)
        if not sp:
            continue
        sid = tok.token_to_id(sp)
        body = tok.encode(m["content"]).ids
        ids.append(sid)
        keep.append(False)                    # 角色标记不学
        ids.extend(body)
        keep.extend([role == "assistant"] * len(body))
    eos = tok.token_to_id("<eos>")
    ids.append(eos)
    keep.append(True)                         # 学「说完该停」

    # 兜底：装配类的回答本身就长，光裁 context 不够。
    # 超长时整段丢掉 context，再不行就硬截尾——保证不越过模型的 max_seq_len。
    while len(ids) > max_len and context:
        cut = 1 + len(tok.encode(context).ids)
        cut = min(cut, len(ids) - 32)
        ids = ids[cut:]
        keep = keep[cut:]
        context = ""
    if len(ids) > max_len:
        ids = ids[:max_len]
        keep = keep[:max_len]

    labels = [ids[i + 1] if keep[i + 1] else IGNORE for i in range(len(ids) - 1)]
    labels.append(IGNORE)                     # 最后一个位置没有下一个 token
    return ids, labels


def collate(batch: list[tuple[list[int], list[int]]], pad: int):
    n = len(batch)
    L = max(len(a) for a, _ in batch)
    ids = torch.full((n, L), pad, dtype=torch.long)
    lab = torch.full((n, L), IGNORE, dtype=torch.long)
    for i, (a, b) in enumerate(batch):
        ids[i, : len(a)] = torch.tensor(a)
        lab[i, : len(b)] = torch.tensor(b)
    return ids, lab


@torch.no_grad()
def evaluate(model, data, pad, device, max_batches=30):
    model.eval()
    tot, cnt = 0.0, 0
    for i in range(0, min(len(data), max_batches * 16), 16):
        ids, lab = collate(data[i:i + 16], pad)
        ids, lab = ids.to(device), lab.to(device)
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=device == "cuda"):
            _, loss = model(ids, labels=lab)
        tot += float(loss)
        cnt += 1
    model.train()
    return tot / max(1, cnt)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(ROOT / "ckpt" / "base.pt"))
    ap.add_argument("--epochs", type=float, default=3.0)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=5e-5)
    ap.add_argument("--out", default=str(ROOT / "ckpt" / "sft.pt"))
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tok = Tokenizer.from_file(str(ROOT / "tokenizer" / "tokenizer.json"))
    pad = tok.token_to_id("<pad>")

    train = [encode_row(tok, r["messages"], r.get("context", ""), max_len=512)
             for r in load_rows(ROOT / "data" / "sft.jsonl")]
    val = [encode_row(tok, r["messages"], r.get("context", ""), max_len=512)
           for r in load_rows(ROOT / "data" / "sft_val.jsonl")]
    print(f"[sft] 训练 {len(train):,} 条 / 验证 {len(val):,} 条")

    ck = torch.load(args.base, map_location=device)
    cfg = ModelConfig(**{k: v for k, v in ck["cfg"].items()
                         if k in ModelConfig.__dataclass_fields__})
    model = EveLM(cfg).to(device)
    model.load_state_dict(ck["model"])
    print(f"[sft] 从 {Path(args.base).name} 起步（参数 {sum(p.numel() for p in model.parameters())/1e6:.1f}M）")

    opt_m, opt_a = build_optimizers(model, lr_muon=0.005, lr_adam=args.lr)
    steps_per_epoch = math.ceil(len(train) / args.batch)
    total = int(steps_per_epoch * args.epochs)
    warmup = max(20, total // 20)
    model.train()

    base_val = evaluate(model, val, pad, device)
    print(f"[sft] 起步验证 loss {base_val:.4f}")

    t0, step, best = time.time(), 0, base_val
    order = list(range(len(train)))
    import random
    random.seed(0)

    while step < total:
        random.shuffle(order)
        for i in range(0, len(order) - args.batch + 1, args.batch):
            if step >= total:
                break
            batch = [train[j] for j in order[i:i + args.batch]]
            ids, lab = collate(batch, pad)
            ids, lab = ids.to(device), lab.to(device)

            lr = args.lr * (step + 1) / warmup if step < warmup else \
                args.lr * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * (step - warmup) / max(1, total - warmup))))
            for g in opt_m.param_groups:
                g["lr"] = lr * 100
            for g in opt_a.param_groups:
                g["lr"] = lr

            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=device == "cuda"):
                _, loss = model(ids, labels=lab)
            opt_m.zero_grad(set_to_none=True)
            opt_a.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt_m.step()
            opt_a.step()

            if step % 50 == 0:
                print(f"  step {step:>5}/{total}  loss {loss.item():.4f}  "
                      f"lr {lr:.1e}  {time.time()-t0:.0f}s", flush=True)
            step += 1

        vl = evaluate(model, val, pad, device)
        print(f"[sft] 第 {step//steps_per_epoch} 轮结束  val {vl:.4f}", flush=True)
        if vl < best:
            best = vl
            torch.save({"model": model.state_dict(), "cfg": cfg.__dict__}, args.out)
            print(f"  -> 保存 {args.out}（val {vl:.4f}）")

    print(f"[sft] 完成，最佳 val {best:.4f}")


if __name__ == "__main__":
    main()

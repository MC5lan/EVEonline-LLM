"""指令微调：在预训练权重上教模型「对话」。

关键点：
  * loss 只在 assistant 段计算（-100 屏蔽 system/user），否则模型会学着去
    「生成问题」，这是新手最常犯的错。
  * chat template 必须和推理时完全一致，否则训练白做。
  * 77M 模型容量小，SFT 容易过拟合，默认只跑 3 epoch，并看验证集 loss。
"""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

import torch
import torch.nn.functional as F
import yaml
from torch.utils.data import DataLoader, Dataset
from tokenizers import Tokenizer

from src.model import EveLM, ModelConfig


def build_example(tok: Tokenizer, messages: list[dict], max_len: int) -> tuple[list[int], list[int]]:
    ids: list[int] = []
    labels: list[int] = []
    for m in messages:
        prefix = f"<|im_start|>{m['role']}\n"
        body = m["content"] + "<|im_end|>\n"
        p_ids = tok.encode(prefix).ids
        b_ids = tok.encode(body).ids

        ids += p_ids + b_ids
        if m["role"] == "assistant":
            labels += [-100] * len(p_ids) + b_ids
        else:
            labels += [-100] * (len(p_ids) + len(b_ids))

    if len(ids) > max_len:
        ids, labels = ids[:max_len], labels[:max_len]
    return ids, labels


class ChatDataset(Dataset):
    def __init__(self, path: str, tok: Tokenizer, max_len: int):
        self.tok = tok
        self.max_len = max_len
        self.rows = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                if r.get("messages"):
                    self.rows.append(r["messages"])

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, i: int):
        return build_example(self.tok, self.rows[i], self.max_len)


def collate(batch, pad_id: int, max_len: int):
    ids = torch.full((len(batch), max_len), pad_id, dtype=torch.long)
    labels = torch.full((len(batch), max_len), -100, dtype=torch.long)
    mask = torch.zeros((len(batch), max_len), dtype=torch.long)
    for i, (x, y) in enumerate(batch):
        ids[i, : len(x)] = torch.tensor(x, dtype=torch.long)
        labels[i, : len(y)] = torch.tensor(y, dtype=torch.long)
        mask[i, : len(x)] = 1
    return ids, labels, mask


def evaluate(model, loader, device, pad_id, max_len) -> float:
    model.eval()
    total, n = 0.0, 0
    with torch.no_grad():
        for ids, labels, _ in loader:
            ids, labels = ids.to(device), labels.to(device)
            with torch.autocast("cuda", dtype=torch.bfloat16):
                _, loss = model(ids, labels=labels)
            total += loss.item()
            n += 1
    model.train()
    return total / max(1, n)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--ckpt", required=True, help="预训练产出的 ckpt/last.pt")
    ap.add_argument("--data", required=True, help="sft.train.jsonl")
    ap.add_argument("--val", default=None, help="sft.val.jsonl")
    ap.add_argument("--tokenizer", default="tokenizer/tokenizer.json")
    ap.add_argument("--out", required=True, help="输出 ckpt，如 ckpt/sft.pt")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--lr", type=float, default=5.0e-5)
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--max-len", type=int, default=512)
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    mcfg = ModelConfig(**cfg["model"])
    device = "cuda" if torch.cuda.is_available() else "cpu"

    tok = Tokenizer.from_file(args.tokenizer)
    pad_id = tok.token_to_id("<|pad|>")

    ck = torch.load(args.ckpt, map_location="cpu", weights_only=False)
    model = EveLM(mcfg)
    model.load_state_dict(ck["model"], strict=True)
    model.to(device)
    print(f"[sft] 已加载 {args.ckpt} @ step {ck.get('step', '?')}")

    train_ds = ChatDataset(args.data, tok, args.max_len)
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True,
                              collate_fn=lambda b: collate(b, pad_id, args.max_len))
    val_loader = None
    if args.val and Path(args.val).exists():
        val_ds = ChatDataset(args.val, tok, args.max_len)
        val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False,
                                collate_fn=lambda b: collate(b, pad_id, args.max_len))
    print(f"[sft] 训练样本 {len(train_ds)} 条")

    decay, no_decay = [], []
    for name, p in model.named_parameters():
        if p.dim() < 2 or "embed_tokens" in name:
            no_decay.append(p)
        else:
            decay.append(p)
    optim = torch.optim.AdamW(
        [{"params": decay, "weight_decay": 0.1},
         {"params": no_decay, "weight_decay": 0.0}],
        lr=args.lr, betas=(0.9, 0.95), eps=1e-8,
    )

    total_steps = len(train_loader) * args.epochs
    warmup = min(50, max(1, total_steps // 20))
    step = 0
    model.train()

    for epoch in range(args.epochs):
        run = 0.0
        for i, (ids, labels, _) in enumerate(train_loader):
            ids, labels = ids.to(device), labels.to(device)

            lr = args.lr * (step + 1) / warmup if step < warmup else \
                args.lr * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * (step - warmup) /
                                                           max(1, total_steps - warmup))))
            for g in optim.param_groups:
                g["lr"] = lr

            optim.zero_grad(set_to_none=True)
            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=(device == "cuda")):
                _, loss = model(ids, labels=labels, use_checkpoint=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optim.step()

            run += loss.item()
            step += 1
            if i % 20 == 0:
                print(f"epoch {epoch+1}/{args.epochs} | step {step}/{total_steps} "
                      f"| loss {run/(i+1):.4f} | lr {lr:.2e}")

        msg = f"[epoch {epoch+1}] train loss {run/max(1,len(train_loader)):.4f}"
        if val_loader is not None:
            msg += f" | val loss {evaluate(model, val_loader, device, pad_id, args.max_len):.4f}"
        print(msg)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"model": model.state_dict(), "model_cfg": mcfg.__dict__,
                "step": step, "stage": "sft"}, out)
    print(f"[sft] 已保存 {out}")


if __name__ == "__main__":
    main()

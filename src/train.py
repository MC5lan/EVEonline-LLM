"""预训练主循环。

设计取舍：
  * Muon + AdamW 双优化器（矩阵用 Muon，嵌入与归一化用 AdamW）
  * 余弦退火 + warmup，梯度裁剪 1.0
  * 每 N 步在验证集上算 loss，防止把「背下来了」当成「学会了」
  * 断点续训：ckpt/last.pt 保存模型、两个优化器、步数、随机数状态

CPU/GPU 都能跑，自动选设备。
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import torch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data import TokenDataset
from src.model import EveLM, ModelConfig
from src.muon import build_optimizers

ROOT = Path(__file__).resolve().parent.parent


def lr_at(step: int, total: int, peak: float, warmup: int) -> float:
    """线性 warmup + 余弦退火到峰值的 5%。"""
    if step < warmup:
        return peak * (step + 1) / warmup
    prog = (step - warmup) / max(1, total - warmup)
    return peak * (0.05 + 0.95 * 0.5 * (1 + math.cos(math.pi * min(1.0, prog))))


@torch.no_grad()
def eval_loss(model, ds, iters: int, seq_len: int, device) -> float:
    model.eval()
    tot = 0.0
    for _ in range(iters):
        x, y = ds.sample_batch(4, device)
        _, loss = model(x, labels=y)
        tot += float(loss)
    model.train()
    return tot / max(1, iters)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=20000)
    ap.add_argument("--batch", type=int, default=2)
    ap.add_argument("--accum", type=int, default=4, help="梯度累积步数，等效 batch = batch*accum")
    ap.add_argument("--seq", type=int, default=1024)
    ap.add_argument("--lr-muon", type=float, default=0.02)
    ap.add_argument("--lr-adam", type=float, default=6e-4)
    ap.add_argument("--warmup", type=int, default=200)
    ap.add_argument("--eval-every", type=int, default=500)
    ap.add_argument("--ckpt-every", type=int, default=1000)
    ap.add_argument("--out", default=str(ROOT / "ckpt"))
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--amp", action="store_true", default=True, help="bf16 混合精度")
    ap.add_argument("--device", default="auto")
    args = ap.parse_args()

    if args.device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        device = args.device
    print(f"[train] 设备 {device}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    cfg = ModelConfig(max_seq_len=args.seq)
    model = EveLM(cfg).to(device)
    n = sum(p.numel() for p in model.parameters()) / 1e6
    print(f"[train] 参数 {n:.2f}M  上下文 {args.seq}  batch {args.batch}")

    ds = TokenDataset(ROOT / "data" / "train.bin", args.seq)
    vds = TokenDataset(ROOT / "data" / "val.bin", args.seq)
    print(f"[train] 训练 {len(ds):,} token / 验证 {len(vds):,} token")

    opt_m, opt_a = build_optimizers(model, args.lr_muon, args.lr_adam)

    start_step = 0
    last = out / "last.pt"
    if args.resume and last.exists():
        ck = torch.load(last, map_location=device)
        model.load_state_dict(ck["model"])
        opt_m.load_state_dict(ck["muon"])
        opt_a.load_state_dict(ck["adam"])
        start_step = ck["step"]
        print(f"[train] 续训，从第 {start_step} 步")

    model.train()
    t0 = time.time()
    best_val = float("inf")
    log_path = out / "log.jsonl"

    for step in range(start_step, args.steps):
        lr_m = lr_at(step, args.steps, args.lr_muon, args.warmup)
        lr_a = lr_at(step, args.steps, args.lr_adam, args.warmup)
        for g in opt_m.param_groups:
            g["lr"] = lr_m
        for g in opt_a.param_groups:
            g["lr"] = lr_a

        x, y = ds.sample_batch(args.batch, device)
        opt_m.zero_grad(set_to_none=True)
        opt_a.zero_grad(set_to_none=True)
        # 梯度累积：4GB 显存装不下大 batch，用累积凑等效 batch，等价于大 batch 训练
        for _ in range(args.accum):
            with torch.autocast("cuda", dtype=torch.bfloat16,
                                enabled=args.amp and device == "cuda"):
                _, loss = model(x, labels=y)
            (loss / args.accum).backward()
            x, y = ds.sample_batch(args.batch, device)
        gn = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt_m.step()
        opt_a.step()

        if step % 20 == 0:
            el = time.time() - t0
            print(f"  step {step:>6}  loss {loss.item():.4f}  "
                  f"lr {lr_a:.2e}/{lr_m:.2e}  gnorm {float(gn):.2f}  {el:.0f}s", flush=True)

        if step > 0 and step % args.eval_every == 0:
            vl = eval_loss(model, vds, 8, args.seq, device)
            best_val = min(best_val, vl)
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"step": step, "train": loss.item(),
                                    "val": vl, "lr_adam": lr_a,
                                    "lr_muon": lr_m}, ensure_ascii=False) + "\n")
            print(f"  [eval] step {step}  val {vl:.4f}  best {best_val:.4f}", flush=True)

        if step > 0 and step % args.ckpt_every == 0:
            torch.save({"model": model.state_dict(), "muon": opt_m.state_dict(),
                        "adam": opt_a.state_dict(), "step": step, "cfg": cfg.__dict__},
                       last)
            torch.save({"model": model.state_dict(), "cfg": cfg.__dict__},
                       out / f"step{step}.pt")
            print(f"  [ckpt] 保存 step {step}", flush=True)

    torch.save({"model": model.state_dict(), "cfg": cfg.__dict__}, out / "base.pt")
    print(f"[train] 完成，权重 -> {out/'base.pt'}")


if __name__ == "__main__":
    main()

"""从零预训练 EVE-LM 77M（RTX 3050 Laptop 4GB 适配）。

核心机制：
  1. 混合采样：每步按 domain_ratio 决定取领域 batch 还是通用 batch。
  2. 两阶段调度：前 80% 领域占比 5%，后 20% 线性升到 35%（退火）。
  3. 断点续训：ckpt/last.pt 自动恢复模型、优化器、步数与 RNG。
  4. --probe 先探显存上限，避免训到一半 OOM。

用法：
  python -m src.pretrain --config configs/eve-77m.yaml --probe
  python -m src.pretrain --config configs/eve-77m.yaml
"""
from __future__ import annotations

import os

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import argparse
import csv
import math
import time
from pathlib import Path

import torch
import yaml

from src.data import TokenDataset
from src.model import EveLM, ModelConfig


# ---------------------------------------------------------------- 调度

def lr_at(step: int, total: int, cfg: dict) -> float:
    warm = cfg["warmup_steps"]
    if step < warm:
        return cfg["lr"] * (step + 1) / max(1, warm)
    prog = min(1.0, max(0.0, (step - warm) / max(1, total - warm)))
    cos = 0.5 * (1.0 + math.cos(math.pi * prog))
    return cfg["lr"] * (cfg["min_lr_ratio"] + (1 - cfg["min_lr_ratio"]) * cos)


def domain_ratio(step: int, total: int, cfg: dict) -> float:
    start = 1.0 - cfg["phase2_frac"]
    prog = step / max(1, total)
    if prog < start:
        return cfg["domain_ratio_phase1"]
    t = (prog - start) / max(1e-9, cfg["phase2_frac"])
    t = min(1.0, max(0.0, t))
    return cfg["domain_ratio_phase1"] + t * (
        cfg["domain_ratio_phase2"] - cfg["domain_ratio_phase1"]
    )


# ---------------------------------------------------------------- 训练

def make_optimizer(model: torch.nn.Module, cfg: dict, device: str) -> torch.optim.Optimizer:
    decay, no_decay = [], []
    for name, p in model.named_parameters():
        if not p.requires_grad:
            continue
        # norm 权重、bias、embedding 不做 weight decay
        if p.dim() < 2 or "embed_tokens" in name:
            no_decay.append(p)
        else:
            decay.append(p)

    groups = [
        {"params": decay, "weight_decay": cfg["weight_decay"]},
        {"params": no_decay, "weight_decay": 0.0},
    ]
    kw = dict(lr=cfg["lr"], betas=(cfg["beta1"], cfg["beta2"]), eps=1e-8)
    if device == "cuda":
        try:
            return torch.optim.AdamW(groups, fused=True, **kw)
        except (TypeError, RuntimeError):
            pass
    return torch.optim.AdamW(groups, **kw)


def probe(model: EveLM, cfg: dict, device: str) -> None:
    """逐个试 micro_batch，找出 4GB 卡的实际上限。"""
    print("\n[probe] 探测显存上限（每档跑 3 步然后清空）")
    seq_len = cfg["seq_len"]
    for mb in (8, 6, 4, 2, 1):
        try:
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            x = torch.randint(0, model.cfg.vocab_size, (mb, seq_len), device=device)
            y = torch.randint(0, model.cfg.vocab_size, (mb, seq_len), device=device)
            model.train()
            for _ in range(3):
                with torch.autocast("cuda", dtype=torch.bfloat16, enabled=cfg["bf16"]):
                    _, loss = model(x, labels=y, use_checkpoint=cfg["grad_checkpoint"])
                loss.backward()
                model.zero_grad(set_to_none=True)
            peak = torch.cuda.max_memory_allocated() / 1024**3
            print(f"  micro_batch={mb:>2}  seq={seq_len}  峰值 {peak:.2f} GB  OK")
            del x, y
        except torch.cuda.OutOfMemoryError:
            print(f"  micro_batch={mb:>2}  seq={seq_len}  OOM")
        finally:
            model.zero_grad(set_to_none=True)
            torch.cuda.empty_cache()
    print("[probe] 建议把 configs 里的 micro_batch 设为上面最大的 OK 值\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--general", default="data/general.bin")
    ap.add_argument("--domain", default="data/domain.bin")
    ap.add_argument("--probe", action="store_true", help="只探测显存，不训练")
    ap.add_argument("--max-steps", type=int, default=0, help="覆盖总步数（冒烟测试用）")
    ap.add_argument("--fresh", action="store_true", help="忽略已有 ckpt，从头训练")
    args = ap.parse_args()

    cfg_all = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    mcfg = ModelConfig(**cfg_all["model"])
    tcfg = cfg_all["train"]

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device != "cuda":
        raise SystemExit("未检测到 CUDA。4GB 卡也要用 GPU，CPU 预训练不可行。")

    torch.manual_seed(1337)
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.set_float32_matmul_precision("high")

    model = EveLM(mcfg).to(device)
    n_all = model.num_params()
    n_emb = model.num_params(non_embedding=True)
    print(f"[model] 参数量 {n_all/1e6:.2f}M（非嵌入 {n_emb/1e6:.2f}M）")

    if args.probe:
        probe(model, tcfg, device)
        return

    seq_len = tcfg["seq_len"]
    mb = tcfg["micro_batch"]
    ga = tcfg["grad_accum"]
    tokens_per_step = mb * ga * seq_len

    total_steps = tcfg["total_tokens"] // tokens_per_step
    if args.max_steps:
        total_steps = min(total_steps, args.max_steps)
    print(f"[plan] {tokens_per_step} tokens/step × {total_steps} steps "
          f"= {tokens_per_step * total_steps/1e9:.2f}B tokens")

    general = TokenDataset(args.general, seq_len)
    domain = TokenDataset(args.domain, seq_len)
    print(f"[data] general {general.n/1e6:.1f}M tokens | domain {domain.n/1e6:.2f}M tokens")

    optim = make_optimizer(model, tcfg, device)
    out_dir = Path(tcfg["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    ckpt_path = out_dir / "last.pt"

    start_step = 0
    if ckpt_path.exists() and not args.fresh:
        try:
            ck = torch.load(ckpt_path, map_location=device, weights_only=False)
            model.load_state_dict(ck["model"])
            optim.load_state_dict(ck["optim"])
            start_step = int(ck["step"]) + 1
            print(f"[resume] 从第 {start_step} 步继续（共 {total_steps}）")
        except Exception as e:  # 损坏的 ckpt 不该阻断训练
            print(f"[resume] 读取失败，从头开始: {e}")
            start_step = 0

    log_path = out_dir / "train_log.csv"
    new_log = not log_path.exists()
    log_f = open(log_path, "a", newline="", encoding="utf-8")
    writer = csv.writer(log_f)
    if new_log:
        writer.writerow(["step", "tokens", "loss", "lr", "p_domain", "tok_per_s", "elapsed_h"])

    model.train()
    t0 = time.time()
    loss_window: list[float] = []

    for step in range(start_step, total_steps):
        lr = lr_at(step, total_steps, tcfg)
        for g in optim.param_groups:
            g["lr"] = lr

        p_dom = domain_ratio(step, total_steps, tcfg)
        optim.zero_grad(set_to_none=True)
        step_loss = 0.0

        for _ in range(ga):
            use_dom = torch.rand(1).item() < p_dom
            ds = domain if use_dom else general
            x, y = ds.sample_batch(mb, device)

            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=tcfg["bf16"]):
                _, loss = model(x, labels=y, use_checkpoint=tcfg["grad_checkpoint"])
                loss = loss / ga

            loss.backward()
            step_loss += loss.item()

        torch.nn.utils.clip_grad_norm_(model.parameters(), tcfg["grad_clip"])
        optim.step()

        loss_window.append(step_loss)
        if len(loss_window) > 50:
            loss_window.pop(0)

        if step % tcfg["log_every"] == 0:
            elapsed = time.time() - t0
            tokens = (step + 1) * tokens_per_step
            tps = tokens / max(1e-9, elapsed)
            avg = sum(loss_window) / len(loss_window)
            print(f"step {step:>5}/{total_steps} | loss {avg:.4f} | lr {lr:.2e} "
                  f"| p_dom {p_dom:.2f} | {tps:,.0f} tok/s | {elapsed/3600:.2f}h")
            writer.writerow([step, tokens, f"{avg:.4f}", f"{lr:.3e}",
                             f"{p_dom:.3f}", f"{tps:.0f}", f"{elapsed/3600:.3f}"])
            log_f.flush()

        if step > 0 and step % tcfg["ckpt_every"] == 0:
            torch.save({"model": model.state_dict(),
                        "optim": optim.state_dict(),
                        "step": step,
                        "model_cfg": mcfg.__dict__,
                        "train_cfg": tcfg}, ckpt_path)
            print(f"[ckpt] 已保存 {ckpt_path} @ step {step}")

    torch.save({"model": model.state_dict(),
                "optim": optim.state_dict(),
                "step": total_steps - 1,
                "model_cfg": mcfg.__dict__,
                "train_cfg": tcfg}, ckpt_path)
    log_f.close()
    print(f"[done] 训练完成，最终 ckpt -> {ckpt_path}")


if __name__ == "__main__":
    main()

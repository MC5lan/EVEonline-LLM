"""Muon 优化器（MomentUm Orthogonalized by Newton-Schulz）。

和 AdamW 的区别：
  AdamW 逐元素自适应步长；Muon 对每个权重矩阵的更新做**正交化**，
  让不同方向的更新量趋于均衡，样本效率更高。

为什么用在我们这里：
  语料只有 400 万 token，每一个 batch 都要榨出最大信息量。
  公开复现（nanoGPT speedrun、Moonlight）显示同等 token 预算下
  Muon 比 AdamW 收敛更快。

只用在哪：二维权重矩阵（注意力、MLP）。
嵌入层、归一化层、词表头仍然用 AdamW——它们不是矩阵乘法意义上的
"变换"，正交化对它们没有意义。
"""
from __future__ import annotations

import torch
from torch.optim import Optimizer


def zeropower_via_newtonschulz(G: torch.Tensor, steps: int = 5, eps: float = 1e-7) -> torch.Tensor:
    """用 Newton-Schulz 迭代逼近 G 的极分解正交因子。"""
    assert G.ndim == 2
    a, b, c = 3.4445, -4.7750, 2.0315
    X = G.to(torch.float32)
    transposed = G.size(0) > G.size(1)
    if transposed:
        X = X.T
    X = X / (X.norm() + eps)
    for _ in range(steps):
        A = X @ X.T
        B = b * A + c * (A @ A)
        X = a * X + B @ X
    if transposed:
        X = X.T
    return X.to(G.dtype)


class Muon(Optimizer):
    def __init__(self, params, lr: float = 0.02, momentum: float = 0.95,
                 nesterov: bool = True, ns_steps: int = 5):
        defaults = dict(lr=lr, momentum=momentum, nesterov=nesterov, ns_steps=ns_steps)
        super().__init__(params, defaults)

    @torch.no_grad()
    def step(self, closure=None):
        loss = None
        if closure is not None:
            with torch.enable_grad():
                loss = closure()

        for group in self.param_groups:
            lr = group["lr"]
            mom = group["momentum"]
            for p in group["params"]:
                if p.grad is None or p.ndim != 2:
                    continue
                g = p.grad
                state = self.state[p]
                if "buf" not in state:
                    state["buf"] = torch.zeros_like(g)
                buf = state["buf"]
                buf.mul_(mom).add_(g)
                if group["nesterov"]:
                    g = g.add(buf, alpha=mom)
                else:
                    g = buf

                O = zeropower_via_newtonschulz(g, steps=group["ns_steps"])
                # 与 AdamW 的量级对齐：按矩阵形状缩放
                scale = max(1.0, p.size(0) / p.size(1)) ** 0.5
                p.add_(O, alpha=-lr * scale)

        return loss


def split_params(model):
    """把参数分成两组：Muon（二维矩阵）与 AdamW（其余）。"""
    muon, adam = [], []
    seen = set()
    for name, p in model.named_parameters():
        if not p.requires_grad or id(p) in seen:
            continue
        seen.add(id(p))
        if p.ndim == 2 and "embed_tokens" not in name and "lm_head" not in name:
            muon.append(p)
        else:
            adam.append(p)
    return muon, adam


def build_optimizers(model, lr_muon: float = 0.02, lr_adam: float = 3e-4,
                     weight_decay: float = 0.1):
    muon_p, adam_p = split_params(model)
    opt_muon = Muon(muon_p, lr=lr_muon, momentum=0.95, nesterov=True)
    opt_adam = torch.optim.AdamW(adam_p, lr=lr_adam, betas=(0.9, 0.95),
                                 weight_decay=weight_decay)
    n_m = sum(p.numel() for p in muon_p) / 1e6
    n_a = sum(p.numel() for p in adam_p) / 1e6
    print(f"[muon] Muon {len(muon_p)} 个矩阵 ({n_m:.1f}M) | "
          f"AdamW {len(adam_p)} 个张量 ({n_a:.1f}M)")
    return opt_muon, opt_adam

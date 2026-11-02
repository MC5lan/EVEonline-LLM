"""EVE-LM 77M —— Llama 式解码器。

设计要点：
  * 模块命名刻意与 HuggingFace LlamaForCausalLM 对齐，
    导出时不用做任何 key 映射，llama.cpp 的 convert_hf_to_gguf.py 直接可读。
  * GQA（10 查询头 / 5 KV 头），head_dim=64。
  * RoPE 表按需缓存，bf16 推理时不额外占显存。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.checkpoint import checkpoint


@dataclass
class ModelConfig:
    vocab_size: int = 24576
    d_model: int = 384
    n_layers: int = 16
    n_heads: int = 8
    n_kv_heads: int = 4
    d_ff: int = 1024
    max_seq_len: int = 1024
    rope_theta: float = 50000.0
    norm_eps: float = 1e-5
    tie_embeddings: bool = True
    qk_norm: bool = True


class RMSNorm(nn.Module):
    def __init__(self, dim: int, eps: float = 1e-5):
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.weight * x * torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + self.eps)


def build_rope(head_dim: int, max_seq_len: int, theta: float, device) -> tuple[torch.Tensor, torch.Tensor]:
    """返回 [T, head_dim] 的 cos / sin（Llama 的 rotate_half 约定）。"""
    inv_freq = 1.0 / (theta ** (torch.arange(0, head_dim, 2, device=device).float() / head_dim))
    t = torch.arange(max_seq_len, device=device).float()
    freqs = torch.outer(t, inv_freq)                       # [T, head_dim/2]
    emb = torch.cat([freqs, freqs], dim=-1)                # [T, head_dim]
    return emb.cos(), emb.sin()


def rotate_half(x: torch.Tensor) -> torch.Tensor:
    x1, x2 = x[..., : x.shape[-1] // 2], x[..., x.shape[-1] // 2:]
    return torch.cat([-x2, x1], dim=-1)


def apply_rope(x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor) -> torch.Tensor:
    # x: [B, H, T, D]   cos/sin: [T, D]
    return x * cos + rotate_half(x) * sin


class Attention(nn.Module):
    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.n_heads = cfg.n_heads
        self.n_kv = cfg.n_kv_heads
        self.head_dim = cfg.d_model // cfg.n_heads
        self.rep = self.n_heads // self.n_kv

        self.q_proj = nn.Linear(cfg.d_model, self.n_heads * self.head_dim, bias=False)
        self.k_proj = nn.Linear(cfg.d_model, self.n_kv * self.head_dim, bias=False)
        self.v_proj = nn.Linear(cfg.d_model, self.n_kv * self.head_dim, bias=False)
        self.o_proj = nn.Linear(self.n_heads * self.head_dim, cfg.d_model, bias=False)

        # QK-Norm：对每个头的 q/k 做 RMSNorm 再进 RoPE。
        # 小模型上这一步几乎不增加参数，却能压住注意力 logits 的爆炸，
        # 允许更高的学习率——数据只有 5M token，学习率给不上去很吃亏。
        self.qk_norm = cfg.qk_norm
        if self.qk_norm:
            self.q_norm = RMSNorm(self.head_dim, cfg.norm_eps)
            self.k_norm = RMSNorm(self.head_dim, cfg.norm_eps)

    def forward(self, x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor) -> torch.Tensor:
        B, T, _ = x.shape
        q = self.q_proj(x).view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(B, T, self.n_kv, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(B, T, self.n_kv, self.head_dim).transpose(1, 2)

        if self.qk_norm:
            q = self.q_norm(q)
            k = self.k_norm(k)

        q = apply_rope(q, cos, sin)
        k = apply_rope(k, cos, sin)

        if self.rep > 1:
            k = k.repeat_interleave(self.rep, dim=1)
            v = v.repeat_interleave(self.rep, dim=1)

        out = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        out = out.transpose(1, 2).reshape(B, T, -1)
        return self.o_proj(out)


class MLP(nn.Module):
    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.gate_proj = nn.Linear(cfg.d_model, cfg.d_ff, bias=False)
        self.up_proj = nn.Linear(cfg.d_model, cfg.d_ff, bias=False)
        self.down_proj = nn.Linear(cfg.d_ff, cfg.d_model, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.down_proj(F.silu(self.gate_proj(x)) * self.up_proj(x))


class Block(nn.Module):
    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.input_layernorm = RMSNorm(cfg.d_model, cfg.norm_eps)
        self.self_attn = Attention(cfg)
        self.post_attention_layernorm = RMSNorm(cfg.d_model, cfg.norm_eps)
        self.mlp = MLP(cfg)

    def forward(self, x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor) -> torch.Tensor:
        x = x + self.self_attn(self.input_layernorm(x), cos, sin)
        x = x + self.mlp(self.post_attention_layernorm(x))
        return x


class LlamaInner(nn.Module):
    """与 HF 的 `model.*` 子模块同名同结构。"""

    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.embed_tokens = nn.Embedding(cfg.vocab_size, cfg.d_model)
        self.layers = nn.ModuleList([Block(cfg) for _ in range(cfg.n_layers)])
        self.norm = RMSNorm(cfg.d_model, cfg.norm_eps)


class EveLM(nn.Module):
    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.cfg = cfg
        self.model = LlamaInner(cfg)
        self.lm_head = nn.Linear(cfg.d_model, cfg.vocab_size, bias=False)
        if cfg.tie_embeddings:
            self.lm_head.weight = self.model.embed_tokens.weight

        self.apply(self._init_weights)
        # 残差投影缩放初始化，稳定深层训练
        for name, p in self.named_parameters():
            if name.endswith("o_proj.weight") or name.endswith("down_proj.weight"):
                nn.init.normal_(p, mean=0.0, std=0.02 / math.sqrt(2 * cfg.n_layers))

        self._cos: Optional[torch.Tensor] = None
        self._sin: Optional[torch.Tensor] = None

    @staticmethod
    def _init_weights(m: nn.Module) -> None:
        if isinstance(m, nn.Linear):
            nn.init.normal_(m.weight, mean=0.0, std=0.02)
            if m.bias is not None:
                nn.init.zeros_(m.bias)
        elif isinstance(m, nn.Embedding):
            nn.init.normal_(m.weight, mean=0.0, std=0.02)

    def _rope(self, T: int, device, dtype) -> tuple[torch.Tensor, torch.Tensor]:
        need = max(T, 1)
        if self._cos is None or self._cos.shape[0] < need or self._cos.device != device:
            full = max(self.cfg.max_seq_len, need)
            self._cos, self._sin = build_rope(
                self.cfg.d_model // self.cfg.n_heads, full, self.cfg.rope_theta, device
            )
        cos = self._cos[:T].to(dtype=dtype)
        sin = self._sin[:T].to(dtype=dtype)
        return cos, sin

    def forward(
        self,
        input_ids: torch.Tensor,
        labels: Optional[torch.Tensor] = None,
        use_checkpoint: bool = False,
    ) -> tuple[torch.Tensor, Optional[torch.Tensor]]:
        B, T = input_ids.shape
        if T > self.cfg.max_seq_len:
            raise ValueError(f"序列长度 {T} 超过 max_seq_len={self.cfg.max_seq_len}")

        x = self.model.embed_tokens(input_ids)
        cos, sin = self._rope(T, x.device, x.dtype)

        for blk in self.model.layers:
            if use_checkpoint and self.training:
                x = checkpoint(blk, x, cos, sin, use_reentrant=False)
            else:
                x = blk(x, cos, sin)

        x = self.model.norm(x)
        logits = self.lm_head(x)

        loss = None
        if labels is not None:
            loss = F.cross_entropy(
                logits.reshape(-1, logits.size(-1)).float(),
                labels.reshape(-1),
                ignore_index=-100,
            )
        return logits, loss

    def num_params(self, non_embedding: bool = False) -> int:
        n = sum(p.numel() for p in self.parameters())
        if non_embedding:
            n -= self.model.embed_tokens.weight.numel()
        return n

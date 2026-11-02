"""运行时冒烟测试（需要 torch，CPU 即可，几秒钟跑完）。

覆盖 model.py / data.py / sft.py 里最容易写错、又最难靠肉眼发现的点：
  * 因果掩码是否真的阻断了未来信息
  * RoPE 是否保范数（写错 rotate_half 会静默退化）
  * GQA 的 repeat_interleave 维度对不对
  * 导出时的 state_dict key 是否严格等于 HF Llama 的命名
  * SFT 的 loss mask 是否只覆盖 assistant 段
  * 小模型能否真的把 loss 降下去（确认反向传播通的）

用法：
  python tools/smoke_test.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.data import TokenDataset            # noqa: E402
from src.model import (ModelConfig, EveLM, apply_rope, build_rope,  # noqa: E402
                       rotate_half)
from src.sft import build_example            # noqa: E402

FAIL = 0


def ok(m: str) -> None:
    print(f"  [ok]   {m}")


def bad(m: str) -> None:
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {m}")


def tiny_cfg() -> ModelConfig:
    return ModelConfig(vocab_size=256, d_model=64, n_layers=2, n_heads=4,
                       n_kv_heads=2, d_ff=128, max_seq_len=128)


def test_rope() -> None:
    print("1) RoPE")
    hd = 64
    cos, sin = build_rope(hd, 32, 10000.0, "cpu")
    if cos.shape != (32, hd):
        bad(f"cos 形状 {cos.shape}，期望 (32, {hd})")
        return
    ok(f"cos/sin 形状 {tuple(cos.shape)}")

    x = torch.randn(2, 4, 16, hd)
    y = apply_rope(x, cos[:16], sin[:16])
    n0 = x.norm(dim=-1)
    n1 = y.norm(dim=-1)
    if not torch.allclose(n0, n1, atol=1e-4):
        bad(f"RoPE 未保范数，最大偏差 {(n0-n1).abs().max():.2e}")
    else:
        ok("旋转保持向量范数（rotate_half 实现正确）")

    # 位置 0 应当是恒等变换
    y0 = apply_rope(x[:, :, :1], cos[:1], sin[:1])
    if not torch.allclose(x[:, :, :1], y0, atol=1e-6):
        bad("位置 0 不是恒等变换")
    else:
        ok("位置 0 恒等")


def test_model() -> None:
    print("2) 前向 / 反向 / 因果性")
    cfg = tiny_cfg()
    model = EveLM(cfg)
    model.train()

    x = torch.randint(0, cfg.vocab_size, (2, 32))
    y = torch.randint(0, cfg.vocab_size, (2, 32))

    logits, loss = model(x, labels=y)
    if logits.shape != (2, 32, cfg.vocab_size):
        bad(f"logits 形状 {tuple(logits.shape)}")
        return
    ok(f"logits 形状 {tuple(logits.shape)}")
    if not torch.isfinite(loss):
        bad("loss 非有限值")
        return
    ok(f"loss = {loss.item():.4f}（随机初始化应≈ln(vocab)={np.log(cfg.vocab_size):.4f}）")

    loss.backward()
    grads = [p.grad for p in model.parameters() if p.grad is not None]
    if not grads:
        bad("没有梯度")
    elif any(not torch.isfinite(g).all() for g in grads):
        bad("梯度含 NaN/Inf")
    else:
        ok(f"{len(grads)} 个参数张量梯度有限")
    model.zero_grad(set_to_none=True)

    # 因果性：只改最后一个 token，前面的 logits 必须完全不变
    model.eval()
    with torch.no_grad():
        a, _ = model(x)
        x2 = x.clone()
        x2[:, -1] = (x2[:, -1] + 1) % cfg.vocab_size
        b, _ = model(x2)
    diff = (a[:, :-1] - b[:, :-1]).abs().max().item()
    if diff > 1e-6:
        bad(f"因果掩码失效：未来 token 影响了前面，最大差 {diff:.2e}")
    else:
        ok("因果掩码正确（未来 token 不影响前面）")

    # 位置编码应当让不同位置的表示不同
    if (a[:, 0] - a[:, 5]).abs().max() < 1e-6:
        bad("不同位置输出完全相同，RoPE 可能没生效")
    else:
        ok("位置编码生效")


def test_gqa() -> None:
    print("3) GQA")
    cfg = tiny_cfg()
    model = EveLM(cfg)
    attn = model.model.layers[0].self_attn
    if attn.head_dim != cfg.d_model // cfg.n_heads:
        bad(f"head_dim {attn.head_dim}")
    else:
        ok(f"head_dim = {attn.head_dim}, rep = {attn.rep}")

    x = torch.randn(1, 8, cfg.d_model)
    cos, sin = build_rope(attn.head_dim, 8, 10000.0, "cpu")
    out = attn(x, cos, sin)
    if out.shape != (1, 8, cfg.d_model):
        bad(f"attention 输出形状 {tuple(out.shape)}")
    else:
        ok("GQA 输出形状正确")


def test_learning() -> None:
    print("4) 能否学会一个简单模式（验证反向传播）")
    cfg = tiny_cfg()
    torch.manual_seed(0)
    model = EveLM(cfg)
    opt = torch.optim.AdamW(model.parameters(), lr=3e-3)

    # 目标：token t 的下一个永远是 (t+1) % vocab
    seq = torch.arange(0, cfg.vocab_size).repeat(4)[:64].unsqueeze(0)
    x, y = seq[:, :-1], seq[:, 1:]

    first = last = None
    for step in range(120):
        opt.zero_grad()
        _, loss = model(x, labels=y)
        loss.backward()
        opt.step()
        if step == 0:
            first = loss.item()
        last = loss.item()

    if last > first * 0.5:
        bad(f"loss 从 {first:.3f} 只降到 {last:.3f}，学习失败")
    else:
        ok(f"loss {first:.3f} -> {last:.3f}")


def test_export_keys() -> None:
    print("5) 导出 key 与 HF Llama 一致")
    cfg = tiny_cfg()
    model = EveLM(cfg)
    got = set(model.state_dict().keys())

    want = {"model.embed_tokens.weight", "model.norm.weight", "lm_head.weight"}
    for i in range(cfg.n_layers):
        p = f"model.layers.{i}."
        want |= {
            p + "input_layernorm.weight",
            p + "post_attention_layernorm.weight",
            p + "self_attn.q_proj.weight",
            p + "self_attn.k_proj.weight",
            p + "self_attn.v_proj.weight",
            p + "self_attn.o_proj.weight",
            p + "mlp.gate_proj.weight",
            p + "mlp.up_proj.weight",
            p + "mlp.down_proj.weight",
        }
    if got != want:
        bad(f"多出 {sorted(got - want)[:4]} / 缺少 {sorted(want - got)[:4]}")
    else:
        ok(f"{len(want)} 个 key 完全匹配")

    if model.lm_head.weight is not model.model.embed_tokens.weight:
        bad("tied embedding 未生效")
    else:
        ok("词嵌入共享（导出时会丢掉 lm_head，靠 tie_word_embeddings 重建）")


def test_dataset() -> None:
    print("6) 二进制数据集")
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "x.bin"
        arr = np.random.randint(0, 256, size=5000, dtype=np.uint16)
        arr.tofile(str(p))
        ds = TokenDataset(p, seq_len=64)
        x, y = ds.sample_batch(3, "cpu")
        if tuple(x.shape) != (3, 64) or tuple(y.shape) != (3, 64):
            bad(f"批次形状 {tuple(x.shape)}")
        elif not torch.equal(x[:, 1:], y[:, :-1]):
            bad("y 不是 x 的右移一位")
        elif x.dtype != torch.long:
            bad(f"dtype {x.dtype}")
        else:
            ok("批次形状 / 位移 / dtype 正确")


def test_sft_mask() -> None:
    print("7) SFT loss mask")

    class StubTok:
        def encode(self, s: str):
            class E:
                ids = [1] * len(s)
            return E()

    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "world"},
    ]
    ids, labels = build_example(StubTok(), msgs, max_len=256)
    if len(ids) != len(labels):
        bad("ids 与 labels 长度不一致")
        return
    n_masked = sum(1 for l in labels if l == -100)
    if n_masked == len(labels):
        bad("全部被 mask，assistant 段没算 loss")
        return
    if n_masked == 0:
        bad("没有任何 mask，user 段也在算 loss")
        return

    # 最后一个非 -100 位置必须落在 assistant 段内
    last = max(i for i, l in enumerate(labels) if l != -100)
    if last < len(labels) - 1:
        bad("assistant 末尾没有被计入 loss")
    else:
        ok(f"mask {n_masked}/{len(labels)}，assistant 段计入 loss")


def main() -> None:
    print("EVE-LM 冒烟测试\n")
    test_rope()
    test_model()
    test_gqa()
    test_learning()
    test_export_keys()
    test_dataset()
    test_sft_mask()
    print()
    if FAIL:
        print(f"结果：{FAIL} 项失败")
        sys.exit(1)
    print("结果：全部通过")


if __name__ == "__main__":
    main()

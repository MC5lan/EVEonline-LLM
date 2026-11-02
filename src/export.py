"""导出成 HuggingFace Llama 格式，供 llama.cpp 转 GGUF。

两个坑：
  1. tied embedding 下 lm_head.weight 与 embed_tokens.weight 是同一块内存，
     safetensors 存共享张量会报错 —— 必须丢掉 lm_head，靠 config 里的
     tie_word_embeddings 让转换脚本自己绑定。
  2. config.json 的 field 名必须严格是 HF Llama 的，写错一个 llama.cpp 就报
     unknown architecture。
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import torch
from safetensors.torch import save_file
from tokenizers import Tokenizer

from src.model import ModelConfig


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--tokenizer", default="tokenizer/tokenizer.json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float16", "float32"])
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    ck = torch.load(args.ckpt, map_location="cpu", weights_only=False)
    raw_cfg = ck.get("model_cfg") or {}
    mcfg = ModelConfig(**raw_cfg) if raw_cfg else ModelConfig()

    state = ck["model"]
    # 处理共享权重
    if mcfg.tie_embeddings:
        state.pop("lm_head.weight", None)

    dtype_map = {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}
    state = {k: v.to(dtype_map[args.dtype]).contiguous() for k, v in state.items()}
    save_file(state, str(out / "model.safetensors"))
    print(f"[export] 权重 -> {out/'model.safetensors'} ({len(state)} tensors)")

    config = {
        "architectures": ["LlamaForCausalLM"],
        "model_type": "llama",
        "hidden_size": mcfg.d_model,
        "intermediate_size": mcfg.d_ff,
        "num_hidden_layers": mcfg.n_layers,
        "num_attention_heads": mcfg.n_heads,
        "num_key_value_heads": mcfg.n_kv_heads,
        "head_dim": mcfg.d_model // mcfg.n_heads,
        "vocab_size": mcfg.vocab_size,
        "max_position_embeddings": mcfg.max_seq_len,
        "rms_norm_eps": mcfg.norm_eps,
        "rope_theta": mcfg.rope_theta,
        "tie_word_embeddings": mcfg.tie_embeddings,
        "hidden_act": "silu",
        "attention_bias": False,
        "mlp_bias": False,
        "bos_token_id": None,
        "eos_token_id": None,
        "torch_dtype": args.dtype,
    }
    (out / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    tok = Tokenizer.from_file(args.tokenizer)
    shutil.copy(args.tokenizer, out / "tokenizer.json")

    tok_cfg = {
        "tokenizer_class": "PreTrainedTokenizerFast",
        "model_max_length": mcfg.max_seq_len,
        "clean_up_tokenization_spaces": False,
        "added_tokens_decoder": {},
    }
    (out / "tokenizer_config.json").write_text(
        json.dumps(tok_cfg, indent=2, ensure_ascii=False), encoding="utf-8")

    specials = {
        "pad_token": "<|pad|>",
        "eos_token": "<|eos|>",
        "additional_special_tokens": ["<|im_start|>", "<|im_end|>"],
    }
    (out / "special_tokens_map.json").write_text(
        json.dumps(specials, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[export] 目录就绪: {out}")
    print("\n接下来（需要 llama.cpp）:")
    print(f"  python llama.cpp/convert_hf_to_gguf.py {out} --outfile {out}/eve-77m-f16.gguf --outtype f16")
    print(f"  llama-quantize {out}/eve-77m-f16.gguf {out}/eve-77m-Q4_K_M.gguf Q4_K_M")
    print(f"  llama-cli -m {out}/eve-77m-Q4_K_M.gguf -p \"<|im_start|>user\\n你好<|im_end|>\\n<|im_start|>assistant\\n\" -n 256")


if __name__ == "__main__":
    main()

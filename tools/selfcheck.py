"""无依赖自检：语法、参数规模、配置文件、评测集格式。

本机没有装 torch，所以这里只做「不需要 torch 也能查」的部分：
  * 全部 .py 能否通过编译
  * 参数量是否与 README 声称的一致（纯算术，不实例化模型）
  * configs 的关键字段是否齐全
  * eval_set.jsonl 每行是否合法 JSON 且字段完整
  * chat 模板里的特殊 token 是否都在 tokenizer 的 SPECIAL_TOKENS 里

用法：
  python tools/selfcheck.py
"""
from __future__ import annotations

import json
import py_compile
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAIL = 0


def ok(msg: str) -> None:
    print(f"  [ok]   {msg}")


def bad(msg: str) -> None:
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {msg}")


def check_syntax() -> None:
    print("1) 语法编译")
    files = sorted(list((ROOT / "src").glob("*.py"))
                   + list((ROOT / "scripts").glob("*.py"))
                   + list((ROOT / "eval").glob("*.py"))
                   + list((ROOT / "rag").glob("*.py"))
                   + list((ROOT / "tools").glob("*.py")))
    for f in files:
        try:
            py_compile.compile(str(f), doraise=True, cfile=str(ROOT / ".pyc_tmp"))
            ok(f.relative_to(ROOT))
        except py_compile.PyCompileError as e:
            bad(f"{f.name}: {e}")
    (ROOT / ".pyc_tmp").unlink(missing_ok=True)


def params_of(vocab: int, d: int, layers: int, heads: int, kv: int, ff: int) -> int:
    hd = d // heads
    per_layer = 2 * d * d + 2 * d * kv * hd + 3 * d * ff + 2 * d
    return vocab * d + layers * per_layer + d


def check_params() -> None:
    print("2) 参数量（纯算术）")
    cfg_path = ROOT / "configs" / "eve-77m.yaml"
    text = cfg_path.read_text(encoding="utf-8")

    def get(key: str) -> int:
        m = re.search(rf"^\s*{key}:\s*(\d+)", text, re.M)
        if not m:
            raise KeyError(key)
        return int(m.group(1))

    try:
        vocab, d, L = get("vocab_size"), get("d_model"), get("n_layers")
        heads, kv, ff = get("n_heads"), get("n_kv_heads"), get("d_ff")
    except KeyError as e:
        bad(f"configs 缺字段 {e}")
        return

    n = params_of(vocab, d, L, heads, kv, ff)
    non_emb = n - vocab * d
    print(f"        vocab={vocab} d_model={d} layers={L} heads={heads} kv={kv} ff={ff}")
    print(f"        总参数 {n/1e6:.2f}M / 非嵌入 {non_emb/1e6:.2f}M")

    if d % heads:
        bad("d_model 不能被 n_heads 整除")
    elif d // heads != 64:
        bad(f"head_dim={d//heads}，llama.cpp 的 GQA 转换通常要 64 或 128")
    else:
        ok("head_dim = 64")

    if heads % kv:
        bad("n_heads 不能被 n_kv_heads 整除")
    else:
        ok(f"GQA 分组 = {heads // kv}")

    if not (70e6 < n < 85e6):
        bad(f"参数量 {n/1e6:.1f}M 与预期 77M 偏差过大")
    else:
        ok("参数量符合预期")


def check_config_keys() -> None:
    print("3) 训练配置字段")
    text = (ROOT / "configs" / "eve-77m.yaml").read_text(encoding="utf-8")
    needed = ["seq_len", "micro_batch", "grad_accum", "total_tokens", "warmup_steps",
              "phase2_frac", "domain_ratio_phase1", "domain_ratio_phase2",
              "lr", "min_lr_ratio", "weight_decay", "beta1", "beta2",
              "grad_clip", "bf16", "grad_checkpoint", "log_every", "ckpt_every", "out_dir"]
    missing = [k for k in needed if not re.search(rf"^\s*{k}:", text, re.M)]
    if missing:
        bad(f"缺字段: {missing}")
    else:
        ok("train 段字段齐全")

    def num(key: str) -> float:
        m = re.search(rf"^\s*{key}:\s*([0-9.eE+-]+)", text, re.M)
        return float(m.group(1)) if m else float("nan")

    mb, ga, seq = num("micro_batch"), num("grad_accum"), num("seq_len")
    total = num("total_tokens")
    tps = mb * ga * seq
    steps = int(total // tps)
    print(f"        {int(tps)} tokens/step × {steps} steps")
    if not (0 <= num("domain_ratio_phase1") <= num("domain_ratio_phase2") <= 1):
        bad("domain 占比区间不合法")
    else:
        ok("领域占比随退火单调上升")
    if num("warmup_steps") > steps * 0.2:
        bad(f"warmup {int(num('warmup_steps'))} 步超过总步数 20%，太长了")
    else:
        ok("warmup 比例合理")


def check_eval_set() -> None:
    print("4) 评测集格式")
    p = ROOT / "eval" / "eval_set.example.jsonl"
    rows = 0
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError as e:
            bad(f"第 {i} 行不是合法 JSON: {e}")
            continue
        if not {"q", "gold", "type"} <= r.keys():
            bad(f"第 {i} 行缺字段")
            continue
        if r["type"] not in {"answerable", "unanswerable"}:
            bad(f"第 {i} 行 type 非法")
            continue
        rows += 1
    ok(f"{rows} 条样例，字段与 type 合法")


def check_rag_eval() -> None:
    print("5) RAG 评测集格式")
    p = ROOT / "rag" / "eval_set.example.jsonl"
    rows = 0
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError as e:
            bad(f"第 {i} 行非法 JSON: {e}")
            continue
        if not r.get("q") or not isinstance(r.get("must"), list) or not r["must"]:
            bad(f"第 {i} 行缺 q 或 must")
            continue
        rows += 1
    ok(f"{rows} 条，q + must 齐全")


def check_special_tokens() -> None:
    print("6) 特殊 token 一致性")
    tok_src = (ROOT / "src" / "tokenize.py").read_text(encoding="utf-8")
    m = re.search(r"SPECIAL_TOKENS\s*=\s*\[(.*?)\]", tok_src, re.S)
    if not m:
        bad("tokenize.py 里找不到 SPECIAL_TOKENS")
        return
    declared = set(re.findall(r'"([^"]+)"', m.group(1)))
    used = set()
    for f in list((ROOT / "src").glob("*.py")) + list((ROOT / "eval").glob("*.py")):
        used |= set(re.findall(r"<\|[a-z_]+\|>", f.read_text(encoding="utf-8")))
    missing = used - declared
    if missing:
        bad(f"代码里用到但 tokenizer 未声明: {missing}")
    else:
        ok(f"声明 {sorted(declared)}，使用处全部覆盖")


def main() -> None:
    print(f"EVE-LM 自检 @ {ROOT}\n")
    check_syntax()
    check_params()
    check_config_keys()
    check_eval_set()
    check_rag_eval()
    check_special_tokens()
    print()
    if FAIL:
        print(f"结果：{FAIL} 项失败")
        sys.exit(1)
    print("结果：全部通过（注意：未验证 torch 运行时，需在有 GPU 的机器上跑 --probe）")


if __name__ == "__main__":
    main()

"""RAG 链路端到端测试（只需 numpy，不需要 torch / 模型 API）。

用 hash 向量后端跑通：建索引 → 混合检索 → 引用回填 → 校验 → 降级。
这套测试的价值在于——它会抓出「改了排序却没改归一化」这类
不会报错、只会让检索慢慢变差的问题。

用法：
  python tools/rag_test.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from rag.ask import backfill, verify  # noqa: E402
from rag.build_index import build  # noqa: E402
from rag.retriever import Retriever, build_prompt, truncate  # noqa: E402

FAIL = 0

DOCS = {
    "mwd.txt": (
        "MWD 即微型跃迁推进器（Microwarpdrive），是 EVE 中最常见的推进装备之一。\n"
        "它能在短时间内提供极高的速度加成，让舰船迅速进入或脱离战斗。\n\n"
        "MWD 的代价是显著增大舰船的信号半径。信号半径变大意味着敌方武器更容易命中，\n"
        "在被锁定和受到伤害的概率上都会明显变差。\n\n"
        "因此使用 MWD 时要注意，在敌方火力密集的区域开启它会大幅提高被击中的概率。\n"
        "这一点与 AB 正好相反。\n"
    ),
    "ab.txt": (
        "AB 即加力燃烧器（Afterburner），提供稳定的速度加成，幅度明显低于 MWD。\n"
        "AB 不会增大信号半径，因此在需要保持隐蔽或降低被命中率时，AB 是更好的选择。\n\n"
        "AB 的电容消耗也远低于 MWD，可以长时间开启，适合长途跃迁和日常巡航。\n"
        "在低安和虫洞中，很多玩家宁可用 AB 而不是 MWD，就是为了不放大信号半径。\n"
    ),
    "t3c.txt": (
        "T3C 指 Tech III 巡洋舰（Strategic Cruiser），由四个子系统组合而成。\n"
        "玩家可以通过更换子系统来大幅改变舰船性能，例如强化火力、防御或探索能力。\n\n"
        "T3C 的四个子系统分别是船体、防御、攻击和推进。\n"
        "不同组合会产生完全不同的舰船，这是 T3C 最大的特点，也是它昂贵的原因。\n\n"
        "T3C 在被打爆时会损失一个子系统，这是它区别于普通巡洋舰的重要机制。\n"
    ),
    "dominix.txt": (
        "多米尼克斯级（Dominix）是盖伦特联邦的战列舰。\n"
        "它以无人机输出为核心，拥有较大的无人机带宽和挂舱，适合长时间 PvE 作战。\n\n"
        "多米尼克斯级的槽位配置偏向低槽，装甲抗性以动能和热能为主。\n"
        "在刷异常空间和做任务时，多米尼克斯级的性价比非常高，是新手常用的刷钱船。\n"
    ),
    "ishtar.txt": (
        "伊什塔尔级（Ishtar）是盖伦特的重型突击巡洋舰，缩写为 HAC。\n"
        "它以重型无人机为核心火力，装甲抗性优秀，常用于虫洞和异常空间作战。\n\n"
        "伊什塔尔级的无人机带宽可以支持多组重型无人机同时作战。\n"
        "相比多米尼克斯级，伊什塔尔级更灵活，但货舱和电量都更紧张。\n"
    ),
}


def ok(m: str) -> None:
    print(f"  [ok]   {m}")


def bad(m: str) -> None:
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {m}")


def make_index(tmp: Path) -> Path:
    src = tmp / "corpus"
    src.mkdir()
    for name, text in DOCS.items():
        (src / name).write_text(text, encoding="utf-8")
    out = tmp / "index"
    build(src, out, provider="hash", dim=512)
    return out


def test_build(idx: Path) -> None:
    print("1) 建索引")
    meta = __import__("json").loads((idx / "meta.json").read_text(encoding="utf-8"))
    if meta["provider"] != "hash":
        bad(f"provider 记录错误: {meta['provider']}")
    else:
        ok(f"5 个文件 -> {meta['n_chunks']} 块，provider=hash dim={meta['dim']}")

    if meta["n_chunks"] < len(DOCS):
        bad(f"块数 {meta['n_chunks']} 少于文件数，切块可能吞内容")
    else:
        ok("块数合理")

    emb = np.load(idx / "emb.npy")
    norms = np.linalg.norm(emb, axis=1)
    if not np.allclose(norms, 1.0, atol=1e-4):
        bad(f"向量未归一化，norm 范围 {norms.min():.3f}~{norms.max():.3f}")
    else:
        ok("向量已 L2 归一化（点积=余弦）")


def test_retrieve(r: Retriever) -> None:
    print("2) 混合检索")

    hits = r.search("MWD 的信号半径有什么影响", k=3)
    if not hits or hits[0]["source"] != "mwd.txt":
        bad(f"「MWD 信号半径」应命中 mwd.txt，实际 {hits[0]['source'] if hits else '无'}")
    else:
        ok(f"「MWD 信号半径」-> {hits[0]['source']}（score {hits[0]['score']:.3f}）")

    hits = r.search("T3C 由什么子系统组成", k=3)
    if not hits or hits[0]["source"] != "t3c.txt":
        bad(f"「T3C 子系统」应命中 t3c.txt，实际 {hits[0]['source'] if hits else '无'}")
    else:
        ok("「T3C 子系统」-> t3c.txt")

    hits = r.search("伊什塔尔级用什么无人机", k=3)
    if not hits or hits[0]["source"] != "ishtar.txt":
        bad(f"「伊什塔尔级」应命中 ishtar.txt，实际 {hits[0]['source'] if hits else '无'}")
    else:
        ok("「伊什塔尔级」-> ishtar.txt")

    hits = r.search("MWD", k=3)
    if not hits or "mwd" not in hits[0]["text"].lower():
        bad("缩写查询未命中含 MWD 的块")
    else:
        ok("缩写查询命中正确（BM25 起作用）")


def test_backfill(r: Retriever) -> None:
    print("3) 引用回填")
    hits = r.search("MWD 的信号半径有什么影响", k=3)

    faithful = "MWD 会显著增大舰船的信号半径，被敌方武器命中的概率明显变差。"
    sup, uns = backfill(faithful, hits)
    if not sup:
        bad("忠实回答却没有任何引用")
    elif uns:
        bad(f"忠实回答出现未定位句子: {uns[0][0][:20]}")
    else:
        ok(f"忠实回答 -> 引用第 {[i+1 for i in sup]} 段，无未定位")

    fabricated = "MWD 会让舰船在跃迁时免于被拦截。"
    sup2, uns2 = backfill(fabricated, hits)
    if not uns2:
        bad("编造内容却全部被判定为有依据")
    else:
        ok(f"编造内容被识别（覆盖率 {uns2[0][1]:.0%}）")


def test_verify(r: Retriever) -> None:
    print("4) 校验")
    hits = r.search("T3C 由什么子系统组成", k=3)

    hard, soft = verify("T3C 由四个子系统组成，可以更换子系统改变性能。", hits)
    if hard:
        bad(f"忠实回答被判为硬问题: {hard}")
    else:
        ok("忠实回答通过数字校验")

    # 中文数字与阿拉伯数字互认
    hard, _ = verify("T3C 有 4 个子系统。", hits)
    if hard:
        bad(f"「4」与原文「四个」未互认: {hard}")
    else:
        ok("「4 个」与原文「四个」互认，不误报")

    hard, _ = verify("T3C 有 7 个子系统，可以更换。", hits)
    if not hard:
        bad("编造的数字 7 没被抓住")
    else:
        ok(f"编造数字被抓住: {hard[0]}")

    hard, soft = verify("", hits)
    if not hard:
        bad("空回答没被判为硬问题")
    else:
        ok("空回答 -> 硬问题（会触发降级）")


def test_prompt(r: Retriever) -> None:
    print("5) prompt 拼装")
    hits = r.search("MWD 的信号半径有什么影响", k=3)
    p = build_prompt("MWD 的信号半径有什么影响", hits, chunk_chars=120)

    if "【资料1】" not in p or "用户问题" not in p:
        bad("prompt 缺少资料编号或问题占位")
    else:
        ok("prompt 含资料编号与问题")

    if "[1]" in p:
        bad("prompt 仍要求模型输出引用编号（应该由程序回填）")
    else:
        ok("未要求模型输出引用，引用交给程序")

    long_hit = hits[0]["text"]
    if len(long_hit) > 120 and long_hit[:120] in p:
        bad("块未被截断")
    else:
        ok("块按 chunk_chars 截断")


def test_truncate() -> None:
    print("6) 截断")
    s = "第一句话在这里。第二句话稍微长一点点。第三句。"
    t = truncate(s, 12)
    if len(t) > 14:
        bad(f"截断后仍过长: {t}")
    elif not t.endswith(("。", "…")):
        bad(f"截断未落在句末: {t}")
    else:
        ok(f"按句末截断 -> {t}")

    if truncate("短句。", 100) != "短句。":
        bad("短文本被改动")
    else:
        ok("短文本原样返回")


def main() -> None:
    print("RAG 端到端测试\n")
    with tempfile.TemporaryDirectory() as d:
        idx = make_index(Path(d))
        test_build(idx)
        r = Retriever(idx, alpha=0.55)
        test_retrieve(r)
        test_backfill(r)
        test_verify(r)
        test_prompt(r)
    test_truncate()
    print()
    if FAIL:
        print(f"结果：{FAIL} 项失败")
        sys.exit(1)
    print("结果：全部通过")


if __name__ == "__main__":
    main()

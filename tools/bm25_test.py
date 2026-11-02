"""BM25 与切块逻辑的离线测试（只需 numpy，不需要 torch）。

这两个模块是纯算法，能在没有 GPU、没有 torch 的机器上直接验证。
检索算错的话，后面接多强的模型都是白搭，所以单独测。

用法：
  python tools/bm25_test.py
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# build_index 顶层 import 了 tqdm，本机可能没装；测试只用到它的切块函数
if "tqdm" not in sys.modules:
    try:
        import tqdm  # noqa: F401
    except ImportError:
        stub = types.ModuleType("tqdm")
        stub.tqdm = lambda x, **kw: x
        sys.modules["tqdm"] = stub

from rag.bm25 import BM25, ascii_terms, tokenize  # noqa: E402
from rag.build_index import chunk, clean, paragraphs  # noqa: E402

FAIL = 0


def ok(m: str) -> None:
    print(f"  [ok]   {m}")


def bad(m: str) -> None:
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {m}")


DOCS = [
    "MWD 即微型跃迁推进器，提供高额速度加成，但会显著增大舰船的信号半径。",
    "AB 即加力燃烧器，速度加成低于 MWD，但不会增大信号半径，适合需要隐蔽的场合。",
    "T3C 是 Tech III 巡洋舰，由四个子系统组合而成，可以大幅定制。",
    "多米尼克斯级是盖伦特联邦的战列舰，主要靠无人机输出，常用于 PvE。",
    "伊什塔尔级是盖伦特重型突击巡洋舰，以重型无人机为核心火力。",
]


def test_tokenize() -> None:
    print("1) 分词")
    toks = tokenize("MWD 增大信号半径 T3C")
    if "mwd" not in toks:
        bad(f"英文术语未整体保留: {toks}")
    else:
        ok("英文缩写整体保留（mwd）")
    if "信号" not in toks:
        bad(f"中文 bigram 缺失: {toks}")
    else:
        ok("中文切成 bigram（信号）")
    if ascii_terms("MWD 和 AB 的区别") != ["mwd", "ab"]:
        bad(f"硬词提取错误: {ascii_terms('MWD 和 AB 的区别')}")
    else:
        ok("硬词只取英文/数字")


def test_bm25() -> None:
    print("2) BM25 排序")
    bm = BM25([tokenize(d) for d in DOCS])
    if bm.n != len(DOCS):
        bad(f"文档数 {bm.n}")

    s = bm.scores(tokenize("信号半径"))
    if s.shape != (len(DOCS),):
        bad(f"分数形状 {s.shape}")
        return
    if s.max() <= 0:
        bad("全部零分")
        return
    ok(f"分数范围 {s.min():.2f} ~ {s.max():.2f}")

    top = int(s.argmax())
    if top not in (0, 1):
        bad(f"「信号半径」命中了错误的文档 {top}: {DOCS[top][:20]}")
    else:
        ok(f"「信号半径」命中第 {top} 篇（MWD/AB 那两篇）")

    s2 = bm.scores(tokenize("T3C 子系统"))
    if int(s2.argmax()) != 2:
        bad(f"「T3C 子系统」应命中第 2 篇，实际 {int(s2.argmax())}")
    else:
        ok("「T3C 子系统」精确命中 T3C 文档")

    # 完全无关的词不应有分数
    s3 = bm.scores(tokenize("量子纠缠"))
    if s3.max() > 1e-6:
        bad("无关词却得了分")
    else:
        ok("无关词得分为 0")


def test_ascii_boost_semantics() -> None:
    print("3) MWD / AB 必须能区分")
    bm = BM25([tokenize(d) for d in DOCS])
    mwd = bm.scores(tokenize("MWD 信号半径"))
    ab = bm.scores(tokenize("AB 信号半径"))
    if int(mwd.argmax()) != 0:
        bad(f"「MWD」未命中第 0 篇，实际 {int(mwd.argmax())}")
    elif int(ab.argmax()) != 1:
        bad(f"「AB」未命中第 1 篇，实际 {int(ab.argmax())}")
    else:
        ok("BM25 能区分 MWD 与 AB（这正是向量检索会错的地方）")


def test_chunk() -> None:
    print("4) 切块")
    text = "\n\n".join(f"第{i}段。" + "EVE 舰船说明" * 20 for i in range(6))
    paras = list(paragraphs(clean(text)))
    if not paras:
        bad("没有解析出段落")
        return
    cs = chunk(paras, target=300, overlap=1)
    if not cs:
        bad("没有切出块")
        return
    ok(f"{len(paras)} 段 -> {len(cs)} 块，平均 {sum(len(c) for c in cs)//len(cs)} 字符")
    if all(len(c) <= 900 for c in cs):
        ok("没有超长块")
    else:
        bad(f"存在超长块 max={max(len(c) for c in cs)}")

    joined = "".join(cs)
    if "第0段" not in joined or "第5段" not in joined:
        bad("首尾内容丢失")
    else:
        ok("首尾内容都在（overlap 没吃掉边界）")


def test_clean() -> None:
    print("5) 清洗")
    raw = "<div>MWD&nbsp;说明</div>\r\n\r\n\r\n\r\n第二段\t\t内容"
    c = clean(raw)
    if "<div>" in c or "&nbsp;" in c:
        bad(f"HTML 未清除: {c}")
    elif "\t" in c or "\r" in c:
        bad("空白未规范")
    elif "\n\n\n" in c:
        bad("多余空行未合并")
    else:
        ok("HTML / 实体 / 空白 / 空行 均处理正确")


def main() -> None:
    print("BM25 与切块测试\n")
    test_tokenize()
    test_bm25()
    test_ascii_boost_semantics()
    test_chunk()
    test_clean()
    print()
    if FAIL:
        print(f"结果：{FAIL} 项失败")
        sys.exit(1)
    print("结果：全部通过")


if __name__ == "__main__":
    main()

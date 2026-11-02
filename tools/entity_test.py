"""实体识别测试：确认「多米尼克斯级」不会被识别成「多米尼克斯级海军型」。

这个 bug 是最容易犯也最致命的——一字之差，槽位和抗性全错。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rag.entities import EntityIndex  # noqa: E402

FAIL = 0


def ok(m: str) -> None:
    print(f"  [ok]   {m}")


def bad(m: str) -> None:
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {m}")


def names(ents) -> list[str]:
    return [e["name"] for e in ents]


def main() -> None:
    print("实体识别测试\n")
    idx = EntityIndex()
    if len(idx) < 1000:
        print(f"  [FAIL] 词表只有 {len(idx)} 条，先跑 tools/build_entities.py")
        sys.exit(1)
    ok(f"词表 {len(idx):,} 条，最长 {idx.max_len} 字")

    print("\n1) 精确性")
    e = idx.find("多米尼克斯级有几个高能量槽")
    if len(e) != 1 or e[0]["name"] != "多米尼克斯级":
        bad(f"应只识别出「多米尼克斯级」，实际 {names(e)}")
    else:
        ok(f"「多米尼克斯级有几个高能量槽」-> {e[0]['name']} (typeID {e[0]['typeID']})")

    e = idx.find("多米尼克斯级海军型的高槽")
    if len(e) != 1 or e[0]["name"] != "多米尼克斯级海军型":
        bad(f"应识别出海军型，实际 {names(e)}")
    else:
        ok(f"「多米尼克斯级海军型」-> {e[0]['name']}")

    print("\n2) 最长匹配优先")
    e = idx.find("伊什塔级和伊什库尔级哪个好")
    if len(e) != 2:
        bad(f"应识别出两个实体，实际 {names(e)}")
    else:
        ok(f"两艘船都识别 -> {names(e)}")

    print("\n3) 英文与大小写")
    e = idx.find("Dominix 的护盾容量")
    if not e or e[0]["name"].lower() != "dominix":
        bad(f"英文名未命中，实际 {names(e)}")
    else:
        ok(f"「Dominix」-> {e[0]['name']} (typeID {e[0]['typeID']})")

    e = idx.find("DOMINIX")
    if not e:
        bad("大写未命中")
    else:
        ok("大写也能命中")

    print("\n4) 不误报")
    for q in ["今天天气不错", "怎么才能赚钱", "MWD 和 AB 的区别"]:
        e = idx.find(q)
        if e:
            bad(f"「{q}」不该命中，实际 {names(e)}")
        else:
            ok(f"「{q}」无实体")

    print("\n5) 查询扩展")
    e = idx.find("多米尼克斯级怎么配")
    exp = idx.expand("多米尼克斯级怎么配", e)
    if "dominix" not in exp.lower():
        bad(f"扩展后没有英文名: {exp}")
    else:
        ok(f"扩展 -> {exp}")

    print()
    if FAIL:
        print(f"结果：{FAIL} 项失败")
        sys.exit(1)
    print("结果：全部通过")


if __name__ == "__main__":
    main()

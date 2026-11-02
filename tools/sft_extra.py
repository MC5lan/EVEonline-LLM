"""多轮 SFT 生成器（拆成独立文件，避免主脚本过长）。"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def from_multiturn(rng) -> list[dict]:
    """多轮追问：教模型处理「那它的中槽呢」这类指代。"""
    out = []
    chain = [("hiSlots", "高能量槽"), ("medSlots", "中能量槽"), ("lowSlots", "低能量槽")]
    path = DATA / "sde_facts.jsonl"
    if not path.exists():
        return out
    for line in path.open(encoding="utf-8"):
        o = json.loads(line)
        if o.get("category") != "舰船":
            continue
        a = o.get("attributes", {})
        zh = o.get("name_zh", "")
        have = [(k, lab) for k, lab in chain if k in a and a[k]]
        if len(have) < 3 or not zh:
            continue
        msgs = [{"role": "user", "content": f"{zh}有几个{have[0][1]}？"},
                {"role": "assistant", "content": f"{int(a[have[0][0]])} 个。"}]
        for k, lab in have[1:]:
            msgs.append({"role": "user",
                         "content": rng.choice([f"那{lab}呢？", f"{lab}呢"])})
            msgs.append({"role": "assistant", "content": f"{int(a[k])} 个。"})
        out.append({"messages": msgs, "source": f"multi:{zh}"})
    return out


def from_fit_multiturn(rng) -> list[dict]:
    """装配追问：先问方案，再问某个槽位装什么。"""
    out = []
    slot_zh = {"hi": "高槽", "med": "中槽", "low": "低槽", "rig": "改装件"}
    path = DATA / "fits.jsonl"
    if not path.exists():
        return out
    seen = set()
    for line in path.open(encoding="utf-8"):
        f = json.loads(line)
        ship = f["ship_zh"]
        if ship in seen:
            continue
        groups: dict[str, list[str]] = {}
        for it in f["items"]:
            lab = slot_zh.get(it["slot"])
            if not lab:
                continue
            q = f"{it['qty']}x " if it.get("qty", 1) > 1 else ""
            groups.setdefault(lab, []).append(q + it["zh"])
        if len(groups) < 2:
            continue
        seen.add(ship)
        lab0 = list(groups)[0]
        msgs = [{"role": "user", "content": f"{ship}怎么配船？"},
                {"role": "assistant",
                 "content": f"{ship}有一套「{f['fit']}」，{lab0}装"
                            f"{'、'.join(groups[lab0])}。"}]
        other = [l for l in groups if l != lab0]
        if other:
            lab1 = other[0]
            msgs.append({"role": "user", "content": f"那{lab1}呢？"})
            msgs.append({"role": "assistant",
                         "content": f"{lab1}装{'、'.join(groups[lab1])}。"})
        out.append({"messages": msgs, "source": f"fitmulti:{ship}"})
    return out

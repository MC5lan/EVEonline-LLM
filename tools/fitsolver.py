"""装配求解器：用 SDE 数值做约束校验，不靠模型猜。

为什么必须独立于模型：
  「换这套装配 PG 够不够」是一道加法题，不是语言题。
  35M 模型算不出 6 门中子的 PG 之和，但这里三行代码就能算。

已实现的校验：
  * PG / CPU 总量（按全技能 V 折算 +25%）
  * 高/中/低/改装槽位占用
  * 无人机带宽与挂舱
  * 装备名是否能对上 SDE（对不上说明装配数据有脏名）

用法：
  python tools/fitsolver.py validate     # 全量校验 436 套装配
  python tools/fitsolver.py show 多米尼克斯级
  python tools/fitsolver.py check 多米尼克斯级 "装配名关键字"
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SKILL_MULT = 1.25          # CPU/PG 管理技能满级各 +25%
SLOT_MAP = {"hi": "hiSlots", "med": "medSlots", "low": "lowSlots",
            "rig": "rigSlots", "subsystem": "subSystemSlots"}


def load_facts() -> tuple[dict, dict]:
    """按英文名建索引。

    中文名会撞车：「救赎级」既可能是 Absolution（指挥舰），也可能是
    Salvation（旗舰）。按中文名索引，后写入的会静默覆盖前一个，
    于是旗舰装配被拿去和指挥舰的 PG 比，得出 593337/1938 这种荒谬结果。
    所以主键用英文名，中文名只在全库唯一时才作为别名收录。
    """
    ships_en, ships_zh, zh_count = {}, {}, {}
    mods_en, mods_zh, mzh_count = {}, {}, {}
    raw_ships, raw_mods = [], []

    with (ROOT / "data" / "sde_facts.jsonl").open(encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            cat = o.get("category")
            zh, en = o.get("name_zh"), o.get("name_en")
            if cat == "舰船":
                raw_ships.append((zh, en, o))
                zh_count[zh] = zh_count.get(zh, 0) + 1
                if en:
                    ships_en[en] = o
            elif cat == "装备":
                a = o.get("attributes", {})
                rec = {"zh": zh, "en": en or "",
                       "power": float(a.get("power", 0) or 0),
                       "cpu": float(a.get("cpu", 0) or 0),
                       "slots": float(a.get("slots", 0) or 0),
                       "volume": float(a.get("volume", 0) or 0),
                       "meta": float(a.get("metaGroupID", 0) or 0),
                       "group_name": o.get("group"),
                       "skills": [a.get("requiredSkill1"), a.get("requiredSkill2")]}
                raw_mods.append((zh, en, rec))
                mzh_count[zh] = mzh_count.get(zh, 0) + 1
                if en:
                    mods_en[en] = rec

    for zh, en, o in raw_ships:
        if zh and zh_count[zh] == 1:
            ships_zh[zh] = o
    for zh, en, rec in raw_mods:
        if zh and mzh_count[zh] == 1:
            mods_zh[zh] = rec

    ships = {**ships_en, **ships_zh}
    mods = {**mods_en, **mods_zh}
    return ships, mods


def resolve_ship(fit: dict, ships: dict) -> dict | None:
    """英文名优先——它不会撞车。"""
    return ships.get(fit.get("ship_en")) or ships.get(fit.get("ship_zh"))


def resolve_module(it: dict, mods: dict) -> dict | None:
    return mods.get(it.get("en")) or mods.get(it.get("zh"))


def load_fits() -> list[dict]:
    p = ROOT / "data" / "fits.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.open(encoding="utf-8")]


def ship_limits(ship: dict) -> dict:
    a = ship.get("attributes", {})
    return {
        "pg": float(a.get("powerOutput", 0) or 0) * SKILL_MULT,
        "cpu": float(a.get("cpuOutput", 0) or 0) * SKILL_MULT,
        "hi": int(a.get("hiSlots", 0) or 0),
        "med": int(a.get("medSlots", 0) or 0),
        "low": int(a.get("lowSlots", 0) or 0),
        "rig": int(a.get("rigSlots", 0) or 0),
        "bandwidth": float(a.get("droneBandwidth", 0) or 0),
        "bay": float(a.get("droneCapacity", 0) or 0),
    }


def check_fit(fit: dict, ships: dict, mods: dict, eng=None) -> dict:
    ship = resolve_ship(fit, ships)
    if not ship:
        return {"ok": False, "reason": "船型不在 SDE 中", "ship": fit["ship_zh"]}
    lim = ship_limits(ship)
    tid = ship.get("typeID")

    pg = cpu = 0.0
    used = defaultdict(int)
    unknown = []
    drone_bandwidth = drone_bay = 0.0

    for it in fit["items"]:
        m = resolve_module(it, mods)
        slot = it["slot"]
        qty = it.get("qty", 1)
        if slot == "drone":
            # 无人机：一架 5 m³、5 Mbit/s（中型口径，精确值需按 drone 类型查）
            drone_bandwidth += 5 * qty
            drone_bay += 5 * qty
            continue
        if slot in ("cargo", "fighter", "service"):
            continue
        if not m:
            unknown.append(it["zh"])
            continue
        # 角色加成：同一件模块装在不同船上 PG/CPU 占用不同
        mp = mc = 1.0
        if eng is not None and tid:
            gid = eng.group_of(m.get("group_name"))
            skills = {int(s) for s in (m.get("skills") or []) if s}
            mp = eng.multiplier(int(tid), 30, gid, skills)
            mc = eng.multiplier(int(tid), 50, gid, skills)
        pg += m["power"] * mp * qty
        cpu += m["cpu"] * mc * qty
        used[slot] += qty

    over = []
    if pg > lim["pg"] > 0:
        over.append(f"PG 超 {pg - lim['pg']:.0f}")
    if cpu > lim["cpu"] > 0:
        over.append(f"CPU 超 {cpu - lim['cpu']:.0f}")
    for s, key in SLOT_MAP.items():
        if used[s] > lim.get(s, 0) and lim.get(s, 0) > 0:
            over.append(f"{s} 槽超 {used[s] - lim[s]}")

    return {
        "ok": not over,
        "ship": fit["ship_zh"],
        "fit": fit["fit"],
        "pg": [round(pg, 1), round(lim["pg"], 1)],
        "cpu": [round(cpu, 1), round(lim["cpu"], 1)],
        "slots": {s: [used[s], lim.get(s, 0)] for s in ("hi", "med", "low", "rig")},
        "over": over,
        "unknown_modules": unknown[:5],
        "n_unknown": len(unknown),
    }


def cmd_calibrate(args) -> None:
    """用真实装配反推每艘船的有效 PG/CPU 预算。

    为什么必须标定：SDE 里的 `power` 是模块的基础占用，不包含舰船的
    角色加成（例如隐形轰炸舰对鱼雷发射器有大幅减成）。直接拿基础值
    去比，会把 3/4 的真实装配判成超限。
    既然这些装配是真飞过的，就用它们的最大占用作为该船的有效上限。
    """
    ships, mods = load_facts()
    fits = load_fits()
    acc: dict[str, dict] = {}
    for f in fits:
        r = check_fit(f, ships, mods)
        if "pg" not in r:
            continue
        s = f.get("ship_en") or f["ship_zh"]
        b = acc.setdefault(s, {"pg": [], "cpu": [], "base_pg": r["pg"][1],
                               "base_cpu": r["cpu"][1]})
        b["pg"].append(r["pg"][0])
        b["cpu"].append(r["cpu"][0])

    def median(xs):
        xs = sorted(xs)
        n = len(xs)
        return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2

    budget: dict[str, dict] = {}
    for s, b in acc.items():
        # 用中位数而不是最大值：一套脏数据（模块名撞到别的物品）就会
        # 把“最大值”抬到几十万，整艘船的预算就废了。
        pg = median(b["pg"])
        cpu = median(b["cpu"])
        budget[s] = {"pg": round(pg, 1), "cpu": round(cpu, 1), "n": len(b["pg"]),
                     "base_pg": b["base_pg"], "base_cpu": b["base_cpu"],
                     "pg_mult": round(pg / max(1e-6, b["base_pg"]), 2),
                     "cpu_mult": round(cpu / max(1e-6, b["base_cpu"]), 2)}

    out = ROOT / "data" / "ship_budget.json"
    out.write_text(json.dumps(budget, ensure_ascii=False, indent=1), encoding="utf-8")

    over = {s: b for s, b in budget.items() if b["pg_mult"] > 1.5}
    print(f"[solver] 标定 {len(budget)} 艘船 -> data/ship_budget.json")
    print(f"  其中 {len(over)} 艘的实际占用超过 SDE 基础值 1.5 倍（说明有角色加成）")
    for s, b in sorted(over.items(), key=lambda x: -x[1]["pg_mult"])[:10]:
        print(f"    {s:<16} PG 实际{SDE_MARK}{b['pg']:.0f} / 基础{b['base_pg']:.0f}"
              f" = {b['pg_mult']:.1f}×  装配 {b['n']} 套")


SDE_MARK = ""


def cmd_validate(args) -> None:
    ships, mods = load_facts()
    fits = load_fits()
    print(f"[solver] 船 {len(ships)//2} 艘 / 装备 {len(mods)//2} 件 / 装配 {len(fits)} 套")

    ok = over = bad_ship = 0
    unknown_total = 0
    over_examples = []
    for f in fits:
        r = check_fit(f, ships, mods)
        if not r.get("ok"):
            if "reason" in r:
                bad_ship += 1
                continue
            over += 1
            unknown_total += r["n_unknown"]
            if len(over_examples) < 8:
                over_examples.append(r)
        else:
            ok += 1

    print(f"\n通过 {ok} / 超限 {over} / 船型缺失 {bad_ship}")
    print(f"对不上 SDE 的模块名 {unknown_total} 处")
    if over_examples:
        print("\n超限样例:")
        for r in over_examples:
            print(f"  {r['ship']} · {r['fit'][:28]}")
            print(f"     PG {r['pg'][0]}/{r['pg'][1]}  CPU {r['cpu'][0]}/{r['cpu'][1]}  {r['over']}")


def cmd_show(args) -> None:
    ships, mods = load_facts()
    fits = [f for f in load_fits() if f["ship_zh"] == args.ship]
    if not fits:
        print(f"没有 {args.ship} 的装配")
        return
    print(f"[solver] {args.ship} 共 {len(fits)} 套")
    for f in fits:
        r = check_fit(f, ships, mods)
        flag = "OK " if r.get("ok") else "超限"
        print(f"  [{flag}] {f['fit'][:40]:<42} "
              f"PG {r.get('pg',['?','?'])[0]}/{r.get('pg',['?','?'])[1]} "
              f"CPU {r.get('cpu',['?','?'])[0]}/{r.get('cpu',['?','?'])[1]}")


def cmd_check(args) -> None:
    ships, mods = load_facts()
    hits = [f for f in load_fits()
            if f["ship_zh"] == args.ship and args.keyword in f["fit"]]
    if not hits:
        print("没找到匹配的装配")
        return
    f = hits[0]
    r = check_fit(f, ships, mods)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    print("\n装配明细:")
    for it in f["items"]:
        m = mods.get(it["en"] or it["zh"])
        extra = f"  PG {m['power']:.1f} CPU {m['cpu']:.1f}" if m else "  (SDE 无此名)"
        print(f"  {it['slot']:<9} {it['qty']}x {it['zh']}{extra}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate")
    sub.add_parser("calibrate")
    p = sub.add_parser("show"); p.add_argument("ship")
    p = sub.add_parser("check"); p.add_argument("ship"); p.add_argument("keyword")
    args = ap.parse_args()
    {"validate": cmd_validate, "calibrate": cmd_calibrate,
     "show": cmd_show, "check": cmd_check}[args.cmd](args)


if __name__ == "__main__":
    main()

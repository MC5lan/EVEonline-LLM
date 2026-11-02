"""用 eos（Pyfa 的装配引擎）做真实校验。

为什么不再自己算：技能、改装件、植入体、角色加成都在效果链里，
自研版本通过率只有 31%。eos 是 Pyfa 的核心，LGPL-2.1，直接复用。

数据链路：
  SDE JSONL --build_eve_db.py--> refs/eve.db --> eos --> PG/CPU

技能处理：eos 的角色系统需要完整技能表，这里先不挂角色，
CPU/PG 管理技能按满级 +25% 手动折算，并在结果里标注。
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYFA = ROOT / "refs" / "pyfa-src" / "Pyfa-master"
DB = ROOT / "refs" / "eve.db"
SKILL_MULT = 1.25


def boot():
    """启动 eos，返回 (getItem, Fit, Ship, Module)。"""
    if str(PYFA) not in sys.path:
        sys.path.insert(0, str(PYFA))
    cs = f"sqlite:///{DB.as_posix()}?check_same_thread=False"
    fake = types.ModuleType("config")
    fake.debug = False
    fake.gamedata_connectionstring = cs
    fake.saveddata_connectionstring = f"sqlite:///{(ROOT/'refs'/'saved.db').as_posix()}"
    sys.modules["config"] = fake

    import eos.config as ec
    ec.debug = False
    ec.gamedataCache = False
    ec.gamedata_connectionstring = cs
    ec.saveddata_connectionstring = fake.saveddata_connectionstring

    from eos import db
    from eos.db import (saveddata_meta, saveddata_engine,
                        gamedata_meta, gamedata_engine)
    saveddata_meta.create_all(saveddata_engine)
    gamedata_meta.create_all(gamedata_engine)

    from eos.db.gamedata.queries import getItem
    from eos.saveddata.fit import Fit
    from eos.saveddata.ship import Ship
    from eos.saveddata.module import Module
    from eos.saveddata.implant import Implant
    return getItem, Fit, Ship, Module, Implant


class SkillReduction:
    """技能对装配占用的减成。

    eos 的 Fit 不会自动接线角色技能（Pyfa 里由 GUI 层挂进去），所以这层自己补。
    数据仍然来自 SDE：技能物品 → 效果 → modifierInfo 写明「改哪个属性、
    作用于需求哪项技能的模块」。

    减成幅度不是固定 5%：技能物品自带「每级减多少」的属性——
      powerNeedBonus(323) 对应 PG，cpuNeedBonus(310) 对应 CPU。
    例如高级武器升级是 -2%/级（满级 -10%），武器升级是 -5%/级（满级 -25%）。
    全部从 SDE 读，不再写死。
    """

    POWER, CPU = 30, 50
    BONUS_ATTR = {30: 323, 50: 310}      # 目标属性 -> 技能上的「每级减成」属性

    def __init__(self, level: int = 5) -> None:
        self.level = level
        self.rules: list[dict] = []
        self.groups_of: dict[int, int] = {}

        cats = {}
        for line in open(ROOT / "data" / "sde" / "categories.jsonl", encoding="utf-8"):
            o = json.loads(line)
            cats[o["_key"]] = (o.get("name") or {}).get("en", "")
        groups = {}
        for line in open(ROOT / "data" / "sde" / "groups.jsonl", encoding="utf-8"):
            o = json.loads(line)
            groups[o["_key"]] = o.get("categoryID")

        skill_types = set()
        for line in open(ROOT / "data" / "sde" / "types.jsonl", encoding="utf-8"):
            o = json.loads(line)
            self.groups_of[o["_key"]] = o.get("groupID")
            gid = o.get("groupID")
            if gid in groups and cats.get(groups[gid]) == "Skill":
                skill_types.add(o["_key"])

        effs = {}
        for line in open(ROOT / "data" / "sde" / "dogmaEffects.jsonl", encoding="utf-8"):
            o = json.loads(line)
            effs[o["_key"]] = o

        for line in open(ROOT / "data" / "sde" / "typeDogma.jsonl", encoding="utf-8"):
            o = json.loads(line)
            if o["_key"] not in skill_types:
                continue
            attrs = {a["attributeID"]: a["value"] for a in o.get("dogmaAttributes", [])}
            for e in o.get("dogmaEffects", []):
                eff = effs.get(e["effectID"])
                if not eff:
                    continue
                for mi in eff.get("modifierInfo") or []:
                    tgt = mi.get("modifiedAttributeID")
                    if tgt not in (self.POWER, self.CPU):
                        continue
                    if mi.get("func") not in ("LocationRequiredSkillModifier",
                                              "LocationGroupModifier"):
                        continue
                    # 每级减成幅度：技能物品自己的 powerNeedBonus / cpuNeedBonus
                    per = attrs.get(self.BONUS_ATTR[tgt])
                    if per is None:
                        continue
                    self.rules.append({
                        "target_skill": mi.get("skillTypeID"),
                        "group": mi.get("groupID"),
                        "attr": tgt,
                        "per_level": abs(float(per)) / 100.0,
                        "name": eff.get("name", ""),
                    })
        print(f"[skill] 影响 PG/CPU 的技能规则 {len(self.rules)} 条")
        seen = {}
        for r in self.rules:
            seen.setdefault(r["name"], r["per_level"])
        for n, v in seen.items():
            print(f"    {n[:56]:<58} 每级 -{v*100:.1f}%")

    def multiplier(self, attr: int, required_skills: set[int],
                   group_id: int | None) -> float:
        m = 1.0
        for r in self.rules:
            if r["attr"] != attr:
                continue
            hit = (r["target_skill"] and r["target_skill"] in required_skills) or \
                  (r["group"] is not None and r["group"] == group_id)
            if hit:
                m *= max(0.0, 1.0 - r["per_level"] * self.level)
        return m


class EosSolver:
    def __init__(self) -> None:
        self.getItem, self.Fit, self.Ship, self.Module, self.Implant = boot()
        # 全技能 V 的角色：技能减成（高级武器升级、CPU/PG 管理）都在这里生效
        from eos.saveddata.character import Character
        self.Character = Character
        self._allv = Character("AllV", defaultLevel=5)
        self._by_zh = {}
        self._by_en = {}
        self._load_names()
        # 技能减成：eos 不接线角色技能，这一层我们自己补
        self.skills = SkillReduction(level=5)
        self._mod_meta = self._load_mod_meta()

    def _load_mod_meta(self) -> dict:
        """模块的 (需求技能集合, 组ID)，用来匹配技能减成规则。"""
        meta = {}
        for line in open(ROOT / "data" / "sde" / "typeDogma.jsonl", encoding="utf-8"):
            o = json.loads(line)
            attrs = {a["attributeID"]: a["value"] for a in o.get("dogmaAttributes", [])}
            skills = {int(attrs[k]) for k in (182, 183, 184) if k in attrs}
            meta[o["_key"]] = (skills, self.skills.groups_of.get(o["_key"]))
        return meta

    def _load_names(self) -> None:
        import sqlite3
        con = sqlite3.connect(DB)
        try:
            for tid, en, zh in con.execute(
                    "SELECT typeID, typeName, typeName_zh FROM invTypes"):
                if en:
                    self._by_en[en] = tid
                if zh:
                    self._by_zh.setdefault(zh, tid)
        except sqlite3.OperationalError:
            # 表名可能不同，退化为全表扫描
            cur = con.execute("SELECT name FROM sqlite_master WHERE type='table'")
            raise SystemExit(f"eve.db 表结构异常: {[r[0] for r in cur]}")
        finally:
            con.close()

    def type_id(self, zh: str | None, en: str | None) -> int | None:
        # 英文名优先：中文名在 SDE 里会撞车（同名建筑/舰船）
        if en:
            tid = self._by_en.get(en)
            if tid is not None:
                return tid
        return self._by_zh.get(zh) if zh else None

    def check(self, fit: dict) -> dict:
        ship_tid = self.type_id(fit.get("ship_zh"), fit.get("ship_en"))
        if not ship_tid:
            return {"ok": False, "reason": "船型缺失", "ship": fit.get("ship_zh")}
        ship_item = self.getItem(ship_tid)
        if not ship_item:
            return {"ok": False, "reason": "SDE 无此船", "ship": fit.get("ship_zh")}

        f = self.Fit(self.Ship(ship_item))
        f.character = self._allv          # 技能按满级，减成才会生效
        placed = 0
        unknown = []
        n_implant = 0
        for it in fit["items"]:
            # 植入体在原始装配文件里放在 cargo 槽，但它会改 PG/CPU 上限，
            # 丢掉就等于凭空少了一截预算。
            is_implant = ("植入体" in it["zh"]) or ("Implant" in (it.get("en") or ""))
            if is_implant:
                tid = self.type_id(it.get("zh"), it.get("en"))
                item = self.getItem(tid) if tid else None
                if item:
                    f.implants.append(self.Implant(item))
                    n_implant += 1
                continue
            if it["slot"] in ("cargo", "drone", "fighter", "service"):
                continue
            tid = self.type_id(it.get("zh"), it.get("en"))
            item = self.getItem(tid) if tid else None
            if not item:
                unknown.append(it["zh"])
                continue
            for _ in range(it.get("qty", 1)):
                f.modules.append(self.Module(item))
                placed += 1

        f.calculateModifiedAttributes()

        pg_cap = f.ship.getModifiedItemAttr("powerOutput")
        cpu_cap = f.ship.getModifiedItemAttr("cpuOutput")
        pg_used = cpu_used = 0.0
        for m in f.modules:
            tid = m.item.ID
            skills, gid = self._mod_meta.get(tid, (set(), None))
            # 技能减成（高级武器升级/武器升级/能量栅格升级/护盾升级）
            fp = self.skills.multiplier(30, skills, gid)
            fc = self.skills.multiplier(50, skills, gid)
            pg_used += (m.getModifiedItemAttr("power") or 0) * fp
            cpu_used += (m.getModifiedItemAttr("cpu") or 0) * fc

        over = []
        if pg_cap and pg_used > pg_cap:
            over.append(f"PG 超 {pg_used - pg_cap:.0f}")
        if cpu_cap and cpu_used > cpu_cap:
            over.append(f"CPU 超 {cpu_used - cpu_cap:.0f}")

        return {"ok": not over, "ship": fit.get("ship_zh"),
                "fit": fit["fit"], "pg": [round(pg_used, 1), round(pg_cap, 1)],
                "cpu": [round(cpu_used, 1), round(cpu_cap, 1)],
                "over": over, "n_unknown": len(unknown),
                "unknown": unknown[:3], "placed": placed}

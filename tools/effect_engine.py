"""最小效果引擎：把舰船的角色加成算进去。

问题：SDE 里模块的 `power`/`cpu` 是基础占用，舰船的效果会把它乘以一个
系数。例如隐形轰炸舰对鱼雷发射器有 0.0035 的乘数（1630 → 5.7），
不乘这一步，任何旗舰外的装配在计算器里都会「超 PG 十倍」。

数据来源全部是 SDE，不含手写规则：
  data/sde/typeDogma.jsonl   舰船：属性值 + 生效的 effectID 列表
  data/sde/dogmaEffects.jsonl 效果：modifierInfo 说明改哪个属性、系数取自哪

只处理装配相关的两件事：power(30) 与 cpu(50) 的修正。
其他属性（伤害、抗性）目前不参与装配合法性判断，不做假实现。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SDE = ROOT / "data" / "sde"

POWER, CPU = 30, 50

# Pyfa 的运算编码（eos/const.py: Operator）
PREASSIGN, PREINCREASE, MULTIPLY, POSTINCREASE, FORCE = range(5)


def _load_jsonl(p: Path) -> dict:
    out = {}
    if not p.exists():
        return out
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            out[o["_key"]] = o
    return out


class EffectEngine:
    def __init__(self) -> None:
        self.effects = _load_jsonl(SDE / "dogmaEffects.jsonl")
        self.typedogma = _load_jsonl(SDE / "typeDogma.jsonl")
        self.groups = _load_jsonl(SDE / "groups.jsonl")
        # groups 的 name 是本地化字典，中文/英文都要能反查
        self.group_id: dict[str, int] = {}
        for gid, g in self.groups.items():
            nm = g.get("name") or {}
            if isinstance(nm, dict):
                for lang in ("zh", "en"):
                    v = nm.get(lang)
                    if v:
                        self.group_id.setdefault(v, gid)
            elif isinstance(nm, str):
                self.group_id.setdefault(nm, gid)
        self._cache: dict[int, list[dict]] = {}
        self.ready = bool(self.effects and self.typedogma)

    def group_of(self, name: str | None) -> int | None:
        return self.group_id.get(name) if name else None

    def ship_modifiers(self, type_id: int) -> list[dict]:
        """返回该舰船对装配模块的 PG/CPU 修正列表。"""
        if type_id in self._cache:
            return self._cache[type_id]
        mods: list[dict] = []
        td = self.typedogma.get(type_id) or {}
        attrs = {a["attributeID"]: float(a["value"])
                 for a in td.get("dogmaAttributes", [])}
        for e in td.get("dogmaEffects", []):
            eff = self.effects.get(e["effectID"])
            if not eff:
                continue
            # 不要按 isDefault 过滤：角色加成效果在 SDE 里都是 isDefault=false，
            # 但它照样参与装配计算（真实装配文件里的 PG 占用就是被它乘过的）。
            for mi in eff.get("modifierInfo") or []:
                target = mi.get("modifiedAttributeID")
                if target not in (POWER, CPU):
                    continue
                src = mi.get("modifyingAttributeID")
                if src is None or src not in attrs:
                    continue
                v = attrs[src]
                # 系数形态有两种：已经是乘数（如 0.0035 / 0.05），
                # 或是百分比（如 -99 表示 -99%）。按数量级区分，
                # 因为 SDE 自己就是这么存的。
                factor = v if 0 < v < 1 else (1.0 + v / 100.0)
                func = mi.get("func", "")
                mods.append({
                    "attr": target,
                    "factor": factor,
                    "func": func,
                    "group": mi.get("groupID"),
                    "skill": mi.get("skillTypeID"),
                    "name": eff.get("name", ""),
                })
        self._cache[type_id] = mods
        return mods

    def multiplier(self, type_id: int, attr: int, group: int | None,
                   skill_ids: set[int] | None = None) -> float:
        """某个模块在整套装配里的 PG/CPU 乘数。"""
        m = 1.0
        for mod in self.ship_modifiers(type_id):
            if mod["attr"] != attr:
                continue
            if mod["func"] == "ItemModifier":
                m *= mod["factor"]
            elif mod["func"] in ("LocationGroupModifier", "LocationGroupModifierSkill"):
                if group is not None and mod["group"] == group:
                    m *= mod["factor"]
            elif mod["func"] in ("LocationRequiredSkillModifier",
                                 "LocationRequiredSkillModifierSkill"):
                if mod["skill"] and skill_ids and mod["skill"] in skill_ids:
                    m *= mod["factor"]
        return m


if __name__ == "__main__":
    eng = EffectEngine()
    print("效果数据:", "就绪" if eng.ready else "缺失", "| 效果", len(eng.effects))
    for name, tid in (("Purifier", 12038), ("Tornado", 4310)):
        mods = eng.ship_modifiers(tid)
        print(f"\n{name} (typeID {tid}) 共 {len(mods)} 条 PG/CPU 修正")
        for m in mods[:6]:
            print(f"  {m['name'][:46]:<48} attr={m['attr']} "
                  f"group={m['group']} ×{m['factor']:.4g}")

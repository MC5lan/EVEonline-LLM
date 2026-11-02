"""把 SDE JSONL 转成 eos（Pyfa 的装配引擎）能读的 eve.db。

为什么走这条：EVE 的装配计算不是「加一加」——技能、改装件、植入体、
角色加成都在效果链里，自己写等于重造 Pyfa。eos 是 LGPL-2.1，可以合法复用，
它要的只是一份按它 schema 组织的 sqlite。

不做的事：不伪造缺失字段（例如 traits 表 SDE 里没有，就不建内容），
不猜单位。所有值都原样搬自 SDE。
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYFA = ROOT / "refs" / "pyfa-src" / "Pyfa-master"
SDE = ROOT / "data" / "sde"
DB = ROOT / "refs" / "eve.db"


def _jsonl(name: str) -> dict:
    p = SDE / name
    out = {}
    if not p.exists():
        return out
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                o = json.loads(line)
                out[o["_key"]] = o
    return out


def _name(d, key="name") -> tuple[str, str]:
    v = d.get(key) or {}
    if isinstance(v, dict):
        return v.get("en", "") or "", v.get("zh", "") or ""
    return str(v), ""


def main() -> None:
    sys.path.insert(0, str(PYFA))
    fake = types.ModuleType("config")
    fake.gamedata_connectionstring = f"sqlite:///{DB.as_posix()}"
    fake.saveddata_connectionstring = f"sqlite:///{(ROOT/'refs'/'saved.db').as_posix()}"
    sys.modules["config"] = fake

    from sqlalchemy import create_engine
    from eos.db.gamedata import (item, attribute, effect, group,
                                 category, metaGroup, unit, metaData)

    if DB.exists():
        DB.unlink()
    engine = create_engine(f"sqlite:///{DB.as_posix()}")
    md = item.Item.__table__.metadata
    md.create_all(engine)

    cats = _jsonl("categories.jsonl")
    groups = _jsonl("groups.jsonl")
    sde_types = _jsonl("types.jsonl")
    typedogma = _jsonl("typeDogma.jsonl")
    dogma_attrs = _jsonl("dogmaAttributes.jsonl")
    dogma_effs = _jsonl("dogmaEffects.jsonl")
    metagroups = _jsonl("metaGroups.jsonl")
    units = _jsonl("dogmaUnits.jsonl")

    print(f"[db] SDE: 类型 {len(sde_types):,} 属性 {len(dogma_attrs):,} "
          f"效果 {len(dogma_effs):,} 组 {len(groups):,}")

    with engine.begin() as conn:
        def ins(table, rows):
            if rows:
                conn.execute(table.insert(), rows)

        ins(category.Category.__table__, [
            {"categoryID": k, "name": _name(v)[0], "name_zh": _name(v)[1],
             "published": int(bool(v.get("published"))), "iconID": v.get("iconID")}
            for k, v in cats.items()])

        ins(group.Group.__table__, [
            {"groupID": k, "name": _name(v)[0], "name_zh": _name(v)[1],
             "published": int(bool(v.get("published"))),
             "categoryID": v.get("categoryID"), "iconID": v.get("iconID")}
            for k, v in groups.items()])

        ins(metaGroup.MetaGroup.__table__, [
            {"metaGroupID": k, "metaGroupName": _name(v)[0], "metaGroupName_zh": _name(v)[1]}
            for k, v in metagroups.items()])

        ins(unit.Unit.__table__, [
            {"unitID": k, "unitName": v.get("name") or _name(v)[0],
             "displayName": _name(v, "displayName")[0],
             "displayName_zh": _name(v, "displayName")[1]}
            for k, v in units.items()])

        # 属性定义
        ins(attribute.AttributeInfo.__table__, [
            {"attributeID": k, "attributeName": _name(v)[0],
             "displayName": _name(v, "displayName")[0],
             "displayName_zh": _name(v, "displayName")[1],
             "defaultValue": v.get("defaultValue"),
             "published": int(bool(v.get("published"))),
             "highIsGood": int(bool(v.get("highIsGood"))),
             "unitID": v.get("unitID"), "iconID": v.get("iconID"),
             "description": _name(v, "description")[0]}
            for k, v in dogma_attrs.items()])

        ins(effect.Effect.__table__, [
            {"effectID": k, "effectName": v.get("name") or "",
             "description": _name(v, "description")[0],
             "published": int(bool(v.get("published"))),
             "isAssistance": int(bool(v.get("isAssistance"))),
             "isOffensive": int(bool(v.get("isOffensive"))),
             "resistanceID": v.get("resistanceAttributeID")}
            for k, v in dogma_effs.items()])

        # 物品
        items, attrs, item_effects = [], [], []
        n_skip = 0
        for tid, t in sde_types.items():
            gid = t.get("groupID")
            if gid not in groups:
                n_skip += 1
                continue
            en, zh = _name(t)
            meta_level = 0
            td = typedogma.get(tid) or {}
            for a in td.get("dogmaAttributes", []):
                if a["attributeID"] == 633:          # metaLevel
                    meta_level = int(a["value"])
                attrs.append({"typeID": tid, "attributeID": a["attributeID"],
                              "value": a["value"]})
            for e in td.get("dogmaEffects", []):
                item_effects.append({"typeID": tid, "effectID": e["effectID"]})
            items.append({
                "typeID": tid, "typeName": en, "typeName_zh": zh,
                "groupID": gid, "published": int(bool(t.get("published"))),
                "marketGroupID": t.get("marketGroupID"),
                "metaGroupID": t.get("metaGroupID"), "metaLevel": meta_level,
                "iconID": t.get("iconID"), "graphicID": t.get("graphicID"),
                "typeDescription": _name(t, "description")[0],
                "typeDescription_zh": _name(t, "description")[1],
                "raceID": t.get("raceID"), "factionID": t.get("factionID"),
            })

        ins(item.Item.__table__, items)
        ins(attribute.Attribute.__table__, attrs)
        ins(effect.ItemEffect.__table__, item_effects)
        ins(metaData.MetaData.__table__, [{"field_name": "clientVersion", "field_value": "0"},
                                          {"field_name": "serverVersion", "field_value": "0"}])

    size = DB.stat().st_size / 1024 / 1024
    print(f"[db] 物品 {len(items):,}（跳过无效组 {n_skip}）"
          f" 属性值 {len(attrs):,} 效果关联 {len(item_effects):,}")
    print(f"[db] -> {DB}  {size:.1f} MB")


if __name__ == "__main__":
    main()

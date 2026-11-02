"""把 SG軍團裝配 / WC裝配 拆成结构化装配记录。

原文是 EVE 装配文件的扁平化导出，形如：
    fitting name=*【军团】xxx description value=shipType value=<localized hint="Barghest">巴盖斯级*</localized>
    hardware slot=low slot 0 type=<localized hint="Signal Amplifier II">信号放大器 II*</localized>
    hardware qty=5 slot=drone bay type=<localized hint="Hornet II">大黄蜂 II*</localized>

产出：
  data/fits.jsonl                一条装配一行，供结构化查询
  canonical/02_舰船与装配/装配库/rewrite.md   可检索的装配条目，一个配置一段
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOC = re.compile(r'<localized hint="([^"]*)">([^<]*?)</localized>')
ITEM = re.compile(r'hardware\s+([^<]*?)type=\s*<localized hint="([^"]*)">([^<]*?)</localized>')
SLOT = re.compile(r"slot=([a-z ]+?)(?:\s+slot\s+(\d+))?(?=\s|$)")
QTY = re.compile(r"qty=(\d+)")

SLOT_ZH = {"hi": "高槽", "med": "中槽", "low": "低槽", "rig": "改装件",
           "subsystem": "子系统", "drone": "无人机", "cargo": "货舱", "service": "服务"}


def parse(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    out = []
    for rec in text.split("fitting name=")[1:]:
        name = rec.split("description")[0].strip().lstrip("*").strip()
        m = re.search(r"shipType value=\s*" + LOC.pattern, rec)
        if not m:
            continue
        ship_en, ship_zh = m.group(1), m.group(2)
        ship_zh = ship_zh.rstrip("*").strip()

        items = []
        for attrs, en, zh in ITEM.findall(rec):
            zh = zh.rstrip("*").strip()
            if not zh or not en:
                continue
            sm = SLOT.search(attrs.strip())
            slot = sm.group(1).strip() if sm else ""
            idx = int(sm.group(2)) if sm and sm.group(2) else None
            qm = QTY.search(attrs)
            qty = int(qm.group(1)) if qm else 1
            if not slot:
                continue
            items.append({"slot": slot, "index": idx, "qty": qty,
                          "en": en, "zh": zh})

        if items:
            out.append({"fit": name, "ship_en": ship_en, "ship_zh": ship_zh,
                        "items": items, "src": path.parent.name})
    return out


def render(fits: list[dict]) -> str:
    """按船分组，一个配置一段。块大小天然落在 200–400 字，正好对齐检索粒度。"""
    by_ship: dict[str, list[dict]] = defaultdict(list)
    for f in fits:
        by_ship[f["ship_zh"]].append(f)

    out = [
        "---",
        "id: canon-fits-lib",
        "title: 装配库（军团装配解析）",
        "domain: 02_舰船与装配",
        "subdomain: 02.1_装配方案",
        "type: canonical",
        "status: drafted",
        "sde_build: 3662168 / 2026-10-30",
        "verified: 2026-11-01",
        "---",
        "",
        "# 装配库（军团装配解析）",
        "",
        f"从军团装配文件解析出 {len(fits):,} 套配置，覆盖 {len(by_ship)} 艘舰船。",
        "每个条目给出船型、配置名与逐槽装配。",
        "",
    ]
    for ship in sorted(by_ship):
        fits_s = by_ship[ship]
        out += [f"## {ship}", "", f"共 {len(fits_s)} 套配置。", ""]
        for f in fits_s:
            # 船名必须写进每个配置的标题：切块会把「## 船名」和下面的配置拆开，
            # 拆开后配置块里就没有船名了，问「XX 怎么配」根本命中不了。
            out.append(f"### {ship} · {f['fit']}")
            groups: dict[str, list[str]] = defaultdict(list)
            for it in f["items"]:
                label = SLOT_ZH.get(it["slot"], it["slot"])
                q = f"{it['qty']}x " if it["qty"] > 1 else ""
                groups[label].append(f"{q}{it['zh']}")
            for label in ["高槽", "中槽", "低槽", "改装件", "子系统", "无人机", "货舱", "服务"]:
                if label in groups:
                    out.append(f"- **{label}**：{'、'.join(groups.pop(label))}")
            for label, vals in groups.items():
                out.append(f"- **{label}**：{'、'.join(vals)}")
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def main() -> None:
    can = ROOT / "canonical" / "02_舰船与装配"
    srcs = [p / "source.md" for p in can.iterdir()
            if p.is_dir() and (p.name.startswith("SG") or p.name.startswith("WC"))]
    all_fits = []
    for s in srcs:
        if s.exists():
            got = parse(s)
            all_fits.extend(got)
            print(f"  {s.parent.name}: {len(got):,} 套")

    slots = Counter(i["slot"] for f in all_fits for i in f["items"])
    print(f"[fits] 共 {len(all_fits):,} 套，槽位分布: {dict(slots.most_common())}")

    out_dir = ROOT / "data"
    with (out_dir / "fits.jsonl").open("w", encoding="utf-8") as f:
        for r in all_fits:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[fits] 结构化记录 -> data/fits.jsonl")

    d = can / "装配库"
    d.mkdir(parents=True, exist_ok=True)
    (d / "source.md").write_text(
        "（本条目由 SG軍團裝配 与 WC裝配 解析生成，原文见同级目录）\n", encoding="utf-8")
    (d / "meta.yaml").write_text(
        "\n".join([f"title: 装配库（军团装配解析）", "domain: 02_舰船与装配",
                   "subdomain: 02.1_装配方案", "origin: SG軍團裝配 / WC裝配",
                   f"chars: {len(all_fits)}", "status: drafted"]) + "\n",
        encoding="utf-8")
    (d / "rewrite.md").write_text(render(all_fits), encoding="utf-8")
    print(f"[fits] 装配库 -> {d.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

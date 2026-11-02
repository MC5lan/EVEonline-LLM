"""批量重写：把 corpus 里的一篇文档变成 canonical 下的结构化条目。

原则（与 canonical/_README.md 一致）：
  * 能对到 SDE 的，数值一律用 SDE，不用原文
  * 对不到 SDE 的，只保留原文里可复述的事实，不做推测
  * 不留"待确认"——无法核实的说法直接不写

对 09_百科 这类条目型文档，重写结果就是"可检索的最小完备条目"。

用法：
  python tools/rewrite_bulk.py --domain 09_百科与资料
  python tools/rewrite_bulk.py --all
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FM = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)


def parse_fm(text: str) -> tuple[dict, str]:
    m = FM.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta, text[m.end():]


def load_facts() -> dict[str, dict]:
    """name_zh / name_en -> fact"""
    out = {}
    p = ROOT / "data" / "sde_facts.jsonl"
    if not p.exists():
        return out
    with p.open(encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            for k in (o.get("name_zh"), o.get("name_en")):
                if k:
                    out[k] = o
    return out


ATTR_ORDER = [
    ("hiSlots", "高能量槽", "{}"), ("medSlots", "中能量槽", "{}"),
    ("lowSlots", "低能量槽", "{}"), ("rigSlots", "改装件槽", "{}"),
    ("hp", "结构值", "{} HP"), ("shieldCapacity", "护盾容量", "{} HP"),
    ("armorHP", "装甲值", "{} HP"), ("cpuOutput", "CPU", "{} TF"),
    ("powerOutput", "能量栅格", "{} MW"), ("capacitorCapacity", "电容", "{} GJ"),
    ("droneBandwidth", "无人机带宽", "{} Mbit/s"), ("droneCapacity", "无人机挂舱", "{} m³"),
    ("maxVelocity", "最大速度", "{} m/s"), ("signatureRadius", "信号半径", "{} m"),
    ("capacity", "货舱", "{} m³"), ("mass", "质量", "{} kg"),
]


def fmt(v) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return str(int(f)) if f == int(f) else f"{f:.2f}".rstrip("0").rstrip(".")


def clean_body(text: str, limit: int = 700) -> str:
    """取原文里第一段像人话的内容。"""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    paras = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 40]
    out = []
    n = 0
    for p in paras:
        if p.startswith("#"):
            continue
        out.append(p)
        n += len(p)
        if n >= limit:
            break
    return "\n\n".join(out) if out else text.strip()[:limit]


def structure_long(title: str, body: str, budget: int = 2600) -> str:
    """把长文压成分节摘要：每个小节保留标题 + 首段。

    长攻略的价值在于结构与要点，不在于逐字复述。原文仍完整保存在 source.md，
    这里产出的是可检索、可训练的浓缩版。
    """
    body = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", body)
    body = re.sub(r"https?://\S+", "", body)
    # 补丁说明用 ===== 小节 ===== 标注章节；统一成 ## 才能被下面的切分认出来
    body = re.sub(r"={3,}\s*([^=\n]{2,40}?)\s*={3,}", r"## \1", body)
    secs = re.split(r"\n(?=#{1,4}\s)", body)

    intro = ""
    blocks = []
    for sec in secs:
        sec = sec.strip()
        if not sec:
            continue
        lines = sec.split("\n")
        if lines[0].startswith("#"):
            head = lines[0].lstrip("#").strip()
            para = " ".join(x.strip() for x in lines[1:] if x.strip())
            if head and para:
                blocks.append((head, para[:260]))
        elif not intro:
            intro = " ".join(x.strip() for x in lines if x.strip())[:300]

    out = [f"# {title}", ""]
    if intro:
        out += [intro, ""]

    # 没有标题的长文（小说、设定集、表格导出）走等距抽样：
    # 每隔一段取一段，保证重写稿覆盖全文脉络，而不是只留开头。
    if not blocks:
        paras = [p.strip().replace("\n", " ") for p in body.split("\n\n")
                 if len(p.strip()) > 40]
        if len(paras) < 6:
            paras = [ln.strip() for ln in body.split("\n") if len(ln.strip()) > 40]
        # 整篇只有一个超长段落（dev blog 常见）：按句号切
        if len(paras) < 3:
            pieces, buf = [], ""
            for sent in re.split(r"(?<=[。！？!?])", body):
                buf += sent
                if len(buf) > 160:
                    pieces.append(buf.strip())
                    buf = ""
            if buf.strip():
                pieces.append(buf.strip())
            paras = [p for p in pieces if len(p) > 40]
        if paras:
            k = min(28, len(paras))
            step = max(1, len(paras) // k)
            picked = [paras[i] for i in range(0, len(paras), step)][:k]
            out += ["> 本文无小节标题，以下为等距抽样，保留全文脉络；完整原文见 source.md。", ""]
            for i, p in enumerate(picked, 1):
                out += [f"## 片段 {i}", "", p[:240], ""]
        return "\n".join(out).rstrip() + "\n"

    used = len(intro)
    for head, para in blocks:
        if used + len(para) > budget:
            break
        out += [f"## {head}", "", para, ""]
        used += len(para)

    # 只有一两个小节、正文却很长（dev blog 常见）：补上等距抽样，避免压成开头
    if used < 800 and len(body) > 3000:
        paras = [p.strip().replace("\n", " ") for p in body.split("\n\n")
                 if len(p.strip()) > 40]
        if len(paras) < 6:
            paras = [ln.strip() for ln in body.split("\n") if len(ln.strip()) > 40]
        if len(paras) < 3:
            pieces, buf = [], ""
            for sent in re.split(r"(?<=[。！？!?])", body):
                buf += sent
                if len(buf) > 160:
                    pieces.append(buf.strip())
                    buf = ""
            if buf.strip():
                pieces.append(buf.strip())
            paras = [p for p in pieces if len(p) > 40]
        if paras:
            k = min(28, len(paras))
            step = max(1, len(paras) // k)
            out += ["## 全文脉络（等距抽样）", ""]
            for i, p in enumerate([paras[j] for j in range(0, len(paras), step)][:k], 1):
                out += [f"- {p[:240]}"]
            out.append("")

    return "\n".join(out).rstrip() + "\n"


def build_entry(title: str, body: str, facts: dict[str, dict], meta: dict) -> str:
    key = title.replace("（已审计）", "").strip()
    fact = facts.get(key) or facts.get(key.replace("级", "")) or facts.get(key + "级")

    lines = [f"# {title}", ""]
    if fact:
        zh, en = fact.get("name_zh", ""), fact.get("name_en", "")
        lines.append(f"**{zh}**（{en}）— {fact.get('category','')} / {fact.get('group','')}")
        attrs = fact.get("attributes", {})
        parts = []
        for k, label, tmpl in ATTR_ORDER:
            v = attrs.get(k)
            if v in (None, 0):
                continue
            parts.append(f"{label} {tmpl.format(fmt(v))}")
        if parts:
            lines += ["", "## 属性", ""] + [f"- {p}" for p in parts]
        desc = clean_body(body, 400)
        lines += ["", "## 说明", "", desc]
        lines += ["", "## 数据来源", "",
                  f"- 数值：SDE {meta.get('sde_build', '3662168 / 2026-10-30')}",
                  "- 文本：原始语料整理"]
    else:
        desc = clean_body(body, 900)
        first = desc.split("\n\n")[0] if desc else ""
        lines.append(first[:200])
        lines += ["", "## 要点", ""]
        for p in desc.split("\n\n")[1:6]:
            p = p.strip().replace("\n", " ")
            if len(p) > 20:
                lines.append(f"- {p}")
        lines += ["", "## 数据来源", "", "- 原始语料整理（无对应 SDE 条目）"]
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--max-chars", type=int, default=60000,
                    help="源文超过这个长度就跳过，留给人工重写")
    ap.add_argument("--long-threshold", type=int, default=6000,
                    help="超过此长度改用分节摘要，而不是条目模板")
    ap.add_argument("--skip", nargs="*", default=[],
                    help="按标题关键字跳过（要人工重写的重点文档）")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    facts = load_facts()
    canon = ROOT / "canonical"
    done = skipped = 0

    for meta_p in sorted(canon.rglob("meta.yaml")):
        d = meta_p.parent
        meta = {}
        for line in meta_p.read_text(encoding="utf-8").splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip()
        if args.domain and meta.get("domain") != args.domain:
            continue
        if not args.all and not args.domain:
            continue
        if meta.get("status") == "drafted":
            skipped += 1
            continue
        src = d / "source.md"
        if not src.exists():
            continue
        body = src.read_text(encoding="utf-8", errors="ignore")
        if len(body) > args.max_chars:
            skipped += 1
            continue
        title = meta.get("title", d.name)
        if any(k in title for k in args.skip):
            skipped += 1
            continue

        # 能对到 SDE 实体的用条目模板；对不到的（攻略、说明、报告）走分节摘要，
        # 否则 3–6K 的攻略会被压成一句开头。
        key = title.replace("级", "")
        is_entity = title in facts or key in facts or (key + "级") in facts
        if is_entity and len(body) <= args.long_threshold:
            text = build_entry(title, body, facts, meta)
        elif len(body) > 1200:
            text = structure_long(title, body)
        else:
            text = build_entry(title, body, facts, meta)
        done += 1
        if args.dry:
            if done <= 2:
                print("=" * 60)
                print(text[:900])
            continue
        (d / "rewrite.md").write_text(text, encoding="utf-8")
        meta_p.write_text("\n".join(f"{k}: {v}" for k, v in {**meta, "status": "drafted"}.items())
                          + "\n", encoding="utf-8")

    print(f"[rewrite] 已重写 {done} 篇，跳过 {skipped} 篇（已处理或过长）")


if __name__ == "__main__":
    main()

"""把 eve_raw 里的各类文档转成纯文本，供切块与索引使用。

支持：docx / xlsx / pdf / xml / zip / txt / md
不支持：doc（旧二进制格式，交给 tools/convert_doc.ps1 用 Word COM 转）

设计取舍：
  * 每个文件输出成一个 .md，带来源头，便于引用回溯
  * 文本按内容 md5 去重（你目录里有大量 "(1)" 副本）
  * 超过 --skip-large-mb 的 PDF 默认跳过（艺术设定集 73MB、小说 67MB，
    要么是图片、要么是剧情，对"专业助手"价值低，且解析极慢）
  * 提取不出文字的 PDF 标记为 scanned（扫描件，需要 OCR，本脚本不做）

用法：
  python tools/convert_docs.py --input D:/Game/eve_raw --out data/converted
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import zipfile
from pathlib import Path

TEXT_EXT = {".txt", ".md"}
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

BAD = re.compile(r'[\\/:*?"<>|]')


def safe_name(stem: str) -> str:
    return BAD.sub("_", stem).strip()[:120]


def header(src: Path, conv: str, chars: int) -> str:
    return (f"<!-- source: {src.as_posix()} -->\n"
            f"<!-- converter: {conv} chars: {chars} -->\n\n")


# ---------------------------------------------------------------- 各格式

def from_docx(p: Path) -> str:
    import docx
    d = docx.Document(str(p))
    parts = [para.text.strip() for para in d.paragraphs if para.text.strip()]
    for t in d.tables:
        rows = []
        for r in t.rows:
            cells = [c.text.strip().replace("\n", " ") for c in r.cells]
            if any(cells):
                rows.append("| " + " | ".join(cells) + " |")
        if rows:
            parts.append("\n".join(rows))
    return "\n\n".join(parts)


def from_xlsx(p: Path, max_rows: int = 3000) -> str:
    import openpyxl
    wb = openpyxl.load_workbook(str(p), read_only=True, data_only=True)
    out = []
    for ws in wb.worksheets:
        rows = []
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i >= max_rows:
                rows.append(f"| …（超过 {max_rows} 行，已截断） |")
                break
            vals = ["" if v is None else str(v).strip() for v in row]
            if any(vals):
                rows.append("| " + " | ".join(vals) + " |")
        if rows:
            out.append(f"## 工作表：{ws.title}\n\n" + "\n".join(rows))
    wb.close()
    return "\n\n".join(out)


def from_pdf(p: Path, max_pages: int = 400) -> tuple[str, str]:
    from pypdf import PdfReader
    r = PdfReader(str(p))
    out = []
    for i, page in enumerate(r.pages[:max_pages]):
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        t = t.strip()
        if t:
            out.append(f"[第 {i+1} 页]\n{t}")
    return "\n\n".join(out), "pdf"


def from_xml(p: Path) -> str:
    from lxml import etree
    tree = etree.parse(str(p))
    lines: list[str] = []
    seen: set[str] = set()
    for el in tree.iter():
        if not isinstance(el.tag, str):
            continue
        attrs = " ".join(f"{k}={v}" for k, v in el.attrib.items())
        txt = (el.text or "").strip()
        if txt and txt not in seen:
            seen.add(txt)
            lines.append(f"{el.tag} {attrs}".strip())
            lines.append(txt)
        elif attrs:
            lines.append(f"{el.tag} {attrs}".strip())
    return "\n".join(lines)


def from_html(p: Path) -> str:
    from lxml import html as LH
    root = LH.parse(str(p)).getroot()
    for bad in root.xpath("//script | //style | //noscript"):
        bad.getparent().remove(bad)
    text = root.text_content()
    return "\n".join(ln.strip() for ln in text.splitlines() if ln.strip())


def from_pptx(p: Path) -> str:
    from pptx import Presentation
    prs = Presentation(str(p))
    out = []
    for i, slide in enumerate(prs.slides, 1):
        parts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                t = shape.text_frame.text.strip()
                if t:
                    parts.append(t)
            if getattr(shape, "has_table", False) and shape.has_table:
                for row in shape.table.rows:
                    cells = [c.text.strip() for c in row.cells]
                    if any(cells):
                        parts.append("| " + " | ".join(cells) + " |")
        if parts:
            out.append(f"## 第 {i} 页\n\n" + "\n".join(parts))
    return "\n\n".join(out)


def from_zip(p: Path) -> str:
    out = []
    with zipfile.ZipFile(str(p)) as z:
        for name in z.namelist():
            if Path(name).suffix.lower() in TEXT_EXT:
                try:
                    t = z.read(name).decode("utf-8", errors="ignore").strip()
                except Exception:
                    continue
                if len(t) > 50:
                    out.append(f"## {name}\n\n{t}")
    return "\n\n".join(out)


# ---------------------------------------------------------------- 主流程

def convert_one(p: Path, args) -> tuple[str, str, str]:
    """返回 (文本, 转换器名, 状态)。"""
    ext = p.suffix.lower()
    if ext == ".docx":
        return from_docx(p), "python-docx", "ok"
    if ext in (".xlsx", ".xlsm"):
        return from_xlsx(p), "openpyxl", "ok"
    if ext == ".pptx":
        return from_pptx(p), "python-pptx", "ok"
    if ext in (".html", ".htm"):
        return from_html(p), "lxml", "ok"
    if ext == ".xml":
        return from_xml(p), "lxml", "ok"
    if ext == ".zip":
        return from_zip(p), "zipfile", "ok"
    if ext in TEXT_EXT:
        return p.read_text(encoding="utf-8", errors="ignore"), "raw", "ok"
    if ext == ".pdf":
        mb = p.stat().st_size / 1024 / 1024
        if mb > args.skip_large_mb:
            return "", "pypdf", f"skipped({mb:.0f}MB>{args.skip_large_mb}MB)"
        text, conv = from_pdf(p)
        if len(text) < 200:
            return text, conv, "scanned(无文本层)"
        return text, conv, "ok"
    return "", "-", "unsupported"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", default="data/converted")
    ap.add_argument("--skip-large-mb", type=float, default=30.0)
    ap.add_argument("--max-chars", type=int, default=2_000_000)
    args = ap.parse_args()

    src = Path(args.input)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in src.rglob("*")
                   if p.is_file() and p.suffix.lower() not in SKIP_EXT)
    print(f"[convert] {len(files)} 个文件待处理\n")

    seen_hash: dict[str, str] = {}
    manifest = []
    t0 = time.time()

    for p in files:
        rel = p.relative_to(src)
        try:
            text, conv, status = convert_one(p, args)
        except Exception as e:
            manifest.append({"src": rel.as_posix(), "status": f"error:{type(e).__name__}",
                             "chars": 0, "converter": "-"})
            print(f"  ✗ {rel.name[:44]:<46} {type(e).__name__}")
            continue

        if status != "ok" or len(text) < 50:
            manifest.append({"src": rel.as_posix(), "status": status, "chars": len(text),
                             "converter": conv})
            mark = "·" if status.startswith("skipped") else "✗"
            print(f"  {mark} {rel.name[:44]:<46} {status}")
            continue

        if len(text) > args.max_chars:
            text = text[: args.max_chars]
            status = f"truncated({args.max_chars})"

        h = hashlib.md5(text.encode("utf-8", "ignore")).hexdigest()
        if h in seen_hash:
            manifest.append({"src": rel.as_posix(), "status": f"dup_of:{seen_hash[h]}",
                             "chars": len(text), "converter": conv})
            print(f"  = {rel.name[:44]:<46} 与已有内容重复")
            continue
        seen_hash[h] = rel.as_posix()

        dst = out_dir / (safe_name(p.stem) + ".md")
        n = 1
        while dst.exists():
            dst = out_dir / f"{safe_name(p.stem)}_{n}.md"
            n += 1
        dst.write_text(header(p, conv, len(text)) + text, encoding="utf-8")

        manifest.append({"src": rel.as_posix(), "out": dst.name, "status": status,
                         "chars": len(text), "converter": conv})
        print(f"  ✓ {rel.name[:44]:<46} {len(text):>8,} 字")

    (out_dir / "_manifest.jsonl").write_text(
        "\n".join(json.dumps(m, ensure_ascii=False) for m in manifest) + "\n",
        encoding="utf-8")

    ok = [m for m in manifest if m["status"] == "ok" or m["status"].startswith("truncated")]
    total = sum(m["chars"] for m in ok)
    print(f"\n[convert] 成功 {len(ok)} / {len(files)}，共 {total:,} 字，"
          f"耗时 {time.time()-t0:.0f}s -> {out_dir}")

    bad = [m for m in manifest if m["status"] not in ("ok",)]
    if bad:
        print("\n未完成：")
        for m in bad[:15]:
            print(f"  {m['status']:<24} {m['src']}")


if __name__ == "__main__":
    main()

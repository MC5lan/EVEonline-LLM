"""拉取官方最新 SDE（只取需要的几张表，不落地整包）。

为什么不全解压：整包 95 MB，解压后接近 400 MB，其中 mapMoons/mapPlanets
占了绝大部分，而我们只需要 types / typeDogma / dogmaAttributes / groups /
categories。这里按需提取，省空间也省时间。

SDE 每季度随版本更新。攻略文本会过时，SDE 不会——所以它必须能一键刷新。

用法：
  python tools/fetch_sde.py                # 有新版本就下
  python tools/fetch_sde.py --check        # 只看版本，不下
  python tools/fetch_sde.py --force        # 强制重下
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LATEST_URL = "https://developers.eveonline.com/static-data/tranquility/latest.jsonl"
ZIP_URL = "https://developers.eveonline.com/static-data/eve-online-static-data-latest-jsonl.zip"
MEMBERS = ["types.jsonl", "typeDogma.jsonl", "dogmaAttributes.jsonl",
           "groups.jsonl", "categories.jsonl", "typeBonus.jsonl",
           "effects.jsonl"]


def latest_build() -> tuple[int, str]:
    req = urllib.request.Request(LATEST_URL, headers={"User-Agent": "eve-lm/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        for line in r.read().decode("utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            if o.get("_key") == "sde":
                return int(o["buildNumber"]), o.get("releaseDate", "")
    raise SystemExit("latest.jsonl 里没找到 sde 记录")


def local_build(sde_dir: Path) -> int:
    p = sde_dir / "_sde.jsonl"
    if not p.exists():
        return 0
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            o = json.loads(line)
            return int(o.get("buildNumber", 0))
    return 0


def download(url: str, dst: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "eve-lm/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        t0 = time.time()
        with dst.open("wb") as f:
            while True:
                chunk = r.read(1024 * 256)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if total and done % (1024 * 1024 * 4) < 1024 * 256:
                    pct = done / total * 100
                    speed = done / max(1e-6, time.time() - t0) / 1024 / 1024
                    print(f"  {pct:5.1f}%  {done/1024/1024:6.1f}/{total/1024/1024:.1f} MB"
                          f"  {speed:.1f} MB/s", flush=True)
    print(f"[fetch] 下载完成 {dst.stat().st_size/1024/1024:.1f} MB")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "data" / "sde"))
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    remote, date = latest_build()
    local = local_build(out)
    print(f"[fetch] 远端 build {remote}（{date}）  本地 build {local or '无'}")

    if remote <= local and not args.force:
        print("[fetch] 已是最新，无需更新")
        return
    if args.check:
        return

    zip_path = out / f"sde_{remote}.zip"
    if not zip_path.exists():
        print(f"[fetch] 下载 {ZIP_URL}")
        download(ZIP_URL, zip_path)

    print("[fetch] 解压所需表")
    with zipfile.ZipFile(zip_path) as z:
        names = {Path(n).name: n for n in z.namelist()}
        for m in MEMBERS:
            if m not in names:
                print(f"  [warn] 包里没有 {m}")
                continue
            with z.open(names[m]) as src, (out / m).open("wb") as dst:
                dst.write(src.read())
            print(f"  {m}  {(out/m).stat().st_size/1024/1024:.1f} MB")

    (out / "_sde.jsonl").write_text(
        json.dumps({"_key": "sde", "buildNumber": remote, "releaseDate": date},
                   ensure_ascii=False) + "\n", encoding="utf-8")

    zip_path.unlink(missing_ok=True)
    print(f"[fetch] 完成 -> {out}（build {remote}）")


if __name__ == "__main__":
    main()

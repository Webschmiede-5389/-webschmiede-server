#!/usr/bin/env python3
"""Download / generate agency website images into public/ (and dist-backup fallback)."""
from __future__ import annotations

import shutil
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "agency-web" / "public"
BACKUP = ROOT / "agency-web" / "dist-backup"

ASSETS = {
    "craftsman.png": "https://images.unsplash.com/photo-1504917595217-d4dc5ebe6122?auto=format&fit=crop&w=1600&q=80",
    "vorher-screenshot.jpg": "https://images.unsplash.com/photo-1551650975-87deedd944c3?w=1200&q=80&auto=format&fit=crop",
    "nachher-screenshot.jpg": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=1200&q=80&auto=format&fit=crop",
}


def download(url: str, dest: Path) -> None:
    print(f"  {dest.name} <- {url[:60]}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Webschmiede-Setup/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        dest.write_bytes(r.read())


def ensure_icon(out: Path) -> None:
    favicon = BACKUP / "favicon.png"
    if not favicon.exists():
        ico = BACKUP / "favicon.ico"
        if ico.exists():
            favicon = ico
    icon = out / "webschmiede-icon.png"
    if favicon.exists():
        shutil.copy2(favicon, icon)
        print(f"OK webschmiede-icon.png (from {favicon.name})")
    else:
        print("WARN favicon fehlt in dist-backup/")


def sync_dir(src: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for name in ASSETS:
        s = src / name
        if s.exists():
            shutil.copy2(s, dest / name)


def main() -> None:
    PUBLIC.mkdir(parents=True, exist_ok=True)
    BACKUP.mkdir(parents=True, exist_ok=True)

    for out in (PUBLIC, BACKUP):
        ensure_icon(out)
        for name, url in ASSETS.items():
            dest = out / name
            try:
                download(url, dest)
                print(f"OK {out.name}/{name} ({dest.stat().st_size // 1024} KB)")
            except Exception as e:
                print(f"ERR {out.name}/{name}: {e}")

    # favicon.png for browser tab
    for out in (PUBLIC, BACKUP):
        icon = out / "webschmiede-icon.png"
        if icon.exists():
            shutil.copy2(icon, out / "favicon.png")

    print("\nFertig. Build: cd agency-web && npm run build")
    print("Deploy: python scripts/deploy_agency.py")


if __name__ == "__main__":
    main()

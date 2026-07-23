#!/usr/bin/env python3
"""Download live agency site static build as backup (not editable source)."""
import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

BASE = "https://digitalehandwerkskunst.de/"
OUT = Path(__file__).resolve().parent.parent / "agency-web" / "dist-backup"


def fetch(url: str) -> requests.Response:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r


def save(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    print(f"  {path.relative_to(OUT.parent)}")


def main():
    print(f"Backup: {BASE} -> {OUT}\n")
    html = fetch(BASE).text
    save(OUT / "index.html", html.encode("utf-8"))

    assets = set(re.findall(r'(?:src|href)="(/assets/[^"]+)"', html))
    for fav in ("/favicon.png", "/favicon.ico"):
        assets.add(fav)

    for rel in sorted(assets):
        url = urljoin(BASE, rel)
        try:
            save(OUT / rel.lstrip("/"), fetch(url).content)
        except Exception as e:
            print(f"  SKIP {rel}: {e}")

    print(f"\nFertig — {len(list(OUT.rglob('*')))} Dateien in dist-backup/")
    print("Hinweis: Das ist der BUILD, nicht der Replit-Quellcode. Für Edits: ZIP aus Replit.")


if __name__ == "__main__":
    main()

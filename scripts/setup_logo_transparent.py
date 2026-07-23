#!/usr/bin/env python3
"""Webschmiede-Logos: weißen Hintergrund entfernen → transparente PNG (gleiche Canvas-Größe)."""
from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CI = ROOT / "app" / "static" / "ci"


def is_background(r: int, g: int, b: int, tolerance: int = 28) -> bool:
    return r >= 255 - tolerance and g >= 255 - tolerance and b >= 255 - tolerance


def flood_remove_white(path_in: Path, path_out: Path, tolerance: int = 28) -> None:
    img = Image.open(path_in).convert("RGBA")
    w, h = img.size
    px = img.load()
    transparent: set[tuple[int, int]] = set()
    q: deque[tuple[int, int]] = deque()

    for x in range(w):
        for y in (0, h - 1):
            if is_background(*px[x, y][:3], tolerance):
                q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if is_background(*px[x, y][:3], tolerance):
                q.append((x, y))

    while q:
        x, y = q.popleft()
        if (x, y) in transparent or x < 0 or y < 0 or x >= w or y >= h:
            continue
        r, g, b, _ = px[x, y]
        if not is_background(r, g, b, tolerance):
            continue
        transparent.add((x, y))
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            q.append((nx, ny))

    for x, y in transparent:
        px[x, y] = (255, 255, 255, 0)

    img.save(path_out, "PNG", optimize=True)
    print(f"OK {path_out.name} ({w}×{h})")


def make_icon_from_horizontal(horizontal: Path, icon_out: Path, size: int = 128) -> None:
    img = Image.open(horizontal).convert("RGBA")
    w, _ = img.size
    side = int(w * 0.38)
    icon = img.crop((0, 0, side, side))
    icon = icon.resize((size, size), Image.Resampling.LANCZOS)
    icon.save(icon_out, "PNG", optimize=True)
    print(f"OK {icon_out.name} ({size}×{size})")


def main() -> None:
    CI.mkdir(parents=True, exist_ok=True)
    src = CI / "webschmiede-logo-horizontal.jpeg"
    if not src.exists():
        raise SystemExit(f"Fehlt: {src}")

    out = CI / "webschmiede-logo-horizontal.png"
    flood_remove_white(src, out)
    make_icon_from_horizontal(out, CI / "webschmiede-icon.png")
    print("\nDeploy: python deploy.py")


if __name__ == "__main__":
    main()

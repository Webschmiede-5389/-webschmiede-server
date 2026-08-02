"""One-shot: copy/resize canonical WebSchmiede brand assets (no redraw)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CI = ROOT / "app" / "static" / "ci"
BRAND = ROOT / "app" / "static" / "brand" / "webschmiede"


def save_square(img: Image.Image, size: int, path: Path) -> None:
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    img2 = img.copy()
    img2.thumbnail((size, size), Image.Resampling.LANCZOS)
    x = (size - img2.width) // 2
    y = (size - img2.height) // 2
    canvas.paste(img2, (x, y), img2)
    canvas.save(path, "PNG", optimize=True)


def dims(p: Path) -> str:
    with Image.open(p) as im:
        return f"{im.width}x{im.height}"


def main() -> None:
    BRAND.mkdir(parents=True, exist_ok=True)
    src_logo = CI / "webschmiede-logo.png"
    src_mark = CI / "webschmiede-logo-mark.png"
    if not src_logo.is_file() or not src_mark.is_file():
        raise SystemExit(f"Missing CI logos under {CI}")

    shutil.copy2(src_logo, BRAND / "logo-horizontal.png")
    shutil.copy2(src_mark, BRAND / "logo-mark.png")

    mark = Image.open(src_mark).convert("RGBA")
    save_square(mark, 32, BRAND / "favicon-32.png")
    save_square(mark, 192, BRAND / "app-icon-192.png")
    save_square(mark, 512, BRAND / "app-icon-512.png")
    shutil.copy2(BRAND / "favicon-32.png", BRAND / "favicon.png")

    (BRAND / "README.md").write_text(
        "# WebSchmiede Brand Assets (canonical)\n\n"
        "Quelle: `docs/agency/ci/BRAND.md`.\n\n"
        "- `logo-horizontal.png` = Kopie von `/ci/webschmiede-logo.png`\n"
        "- `logo-mark.png` = Kopie von `/ci/webschmiede-logo-mark.png`\n"
        "- Favicon/App-Icons = Resize derselben Mark-Datei (kein Neuzeichnen)\n\n"
        "SVG-Originale fehlen im Repo — bewusst **nicht** erfunden.\n"
        "Kundenlogos unter `app/static/brand/{slug}-logo.png` bleiben unberührt.\n",
        encoding="utf-8",
    )

    manifest = {
        "brand": "WebSchmiede",
        "subtitle": "Digitale Handwerkskunst",
        "generated_at": "2026-08-02",
        "source_of_truth": "docs/agency/ci/BRAND.md",
        "svg_status": "unavailable_no_redraw",
        "assets": [
            {
                "asset_name": "logo-horizontal",
                "path": "/brand/webschmiede/logo-horizontal.png",
                "source_path": "/ci/webschmiede-logo.png",
                "usage": "headers, documents, brand lockup full",
                "dimensions": dims(BRAND / "logo-horizontal.png"),
                "format": "png",
                "canonical": True,
                "deprecated_replacements": [
                    "/ci/webschmiede-logo-horizontal.png",
                    "/ci/webschmiede-logo-horizontal.jpeg",
                    "/ci/webschmiede-logo-icon.png",
                ],
            },
            {
                "asset_name": "logo-mark",
                "path": "/brand/webschmiede/logo-mark.png",
                "source_path": "/ci/webschmiede-logo-mark.png",
                "usage": "sidebar, compact lockup, icon source",
                "dimensions": dims(BRAND / "logo-mark.png"),
                "format": "png",
                "canonical": True,
                "deprecated_replacements": [
                    "CSS letter W placeholder",
                    "/ci/webschmiede-logo-icon.png",
                ],
            },
            {
                "asset_name": "favicon",
                "path": "/brand/webschmiede/favicon.png",
                "usage": "browser tab derived from mark",
                "dimensions": dims(BRAND / "favicon.png"),
                "format": "png",
                "canonical": True,
                "deprecated_replacements": [],
            },
            {
                "asset_name": "app-icon-192",
                "path": "/brand/webschmiede/app-icon-192.png",
                "usage": "PWA / apple-touch",
                "dimensions": dims(BRAND / "app-icon-192.png"),
                "format": "png",
                "canonical": True,
                "deprecated_replacements": [],
            },
            {
                "asset_name": "app-icon-512",
                "path": "/brand/webschmiede/app-icon-512.png",
                "usage": "PWA large",
                "dimensions": dims(BRAND / "app-icon-512.png"),
                "format": "png",
                "canonical": True,
                "deprecated_replacements": [],
            },
            {
                "asset_name": "logo-horizontal.svg",
                "path": None,
                "usage": "planned when official SVG export exists",
                "dimensions": None,
                "format": "svg",
                "canonical": False,
                "status": "MISSING_NO_REDRAW",
                "deprecated_replacements": [],
            },
            {
                "asset_name": "logo-mark.svg",
                "path": None,
                "usage": "planned when official SVG export exists",
                "dimensions": None,
                "format": "svg",
                "canonical": False,
                "status": "MISSING_NO_REDRAW",
                "deprecated_replacements": [],
            },
            {
                "asset_name": "favicon.svg",
                "path": None,
                "usage": "planned when official SVG export exists",
                "dimensions": None,
                "format": "svg",
                "canonical": False,
                "status": "MISSING_NO_REDRAW",
                "deprecated_replacements": [],
            },
        ],
    }
    (BRAND / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("wrote", BRAND)


if __name__ == "__main__":
    main()

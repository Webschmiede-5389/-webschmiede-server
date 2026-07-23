# -*- coding: utf-8 -*-
"""Dark Plurality: Katalog laden + Watch-URLs für Demand-Report."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CATALOG = Path(__file__).resolve().parent / "dark_sources.json"


def load_catalog() -> dict[str, Any]:
    if not CATALOG.exists():
        return {"verticals": {}}
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def watch_urls(*, verticals: list[str] | None = None) -> list[dict[str, str]]:
    cat = load_catalog()
    verts = verticals or list((cat.get("verticals") or {}).keys())
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for vid in verts:
        block = (cat.get("verticals") or {}).get(vid) or {}
        for src in block.get("sources") or []:
            url = (src.get("url") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            out.append(
                {
                    "portal": src.get("portal") or "Dark",
                    "label": f"{vid}: {src.get('label') or src.get('id')}",
                    "url": url,
                    "hint": src.get("hint") or src.get("type") or "",
                }
            )
    return out


def catalog_summary() -> dict[str, int]:
    cat = load_catalog()
    summary: dict[str, int] = {}
    for vid, block in (cat.get("verticals") or {}).items():
        summary[vid] = len(block.get("sources") or [])
    return summary

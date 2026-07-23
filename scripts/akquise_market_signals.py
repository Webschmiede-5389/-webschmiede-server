#!/usr/bin/env python3
"""Markt-Signale: Jobs + Insolvenz/Umbruch in der Region (Google News RSS)."""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "akquise" / "reports"
OUT.mkdir(parents=True, exist_ok=True)

QUERIES = [
    ("jobs", "Geselle gesucht Euskirchen OR Mechernich OR Handwerk"),
    ("jobs", "Mitarbeiter gesucht Restaurant Euskirchen OR Mechernich"),
    ("jobs", "Azubi gesucht Dachdecker OR Elektriker Eifel"),
    ("insolvenz", "Insolvenz Euskirchen OR Mechernich OR Kreis Euskirchen"),
    ("insolvenz", "Geschäftsschließung Euskirchen OR Mechernich"),
    ("neuoeffnung", "Neueröffnung Restaurant OR Imbiss Euskirchen OR Mechernich"),
    ("neuoeffnung", "Neueröffnung Handwerk Euskirchen OR Mechernich"),
]


def fetch(q: str, ua: str) -> list[dict]:
    url = (
        "https://news.google.com/rss/search?q="
        + quote_plus(q)
        + "&hl=de&gl=DE&ceid=DE:de"
    )
    try:
        r = requests.get(url, timeout=25, headers={"User-Agent": ua})
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception as exc:
        return [{"error": str(exc)[:100], "query": q}]
    items = []
    for item in root.findall(".//item")[:20]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if title:
            items.append({"title": title[:220], "link": link, "query": q})
    return items


def main() -> int:
    ua = "Webschmiede-Akquise-Market/1.0"
    hits = []
    seen = set()
    for kind, q in QUERIES:
        for it in fetch(q, ua):
            if it.get("error"):
                continue
            key = it["title"].lower()
            if key in seen:
                continue
            seen.add(key)
            it["kind"] = kind
            hits.append(it)
    report = {
        "date": date.today().isoformat(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(hits),
        "jobs": [h for h in hits if h["kind"] == "jobs"],
        "insolvenz": [h for h in hits if h["kind"] == "insolvenz"],
        "neuoeffnung": [h for h in hits if h["kind"] == "neuoeffnung"],
        "note": "Öffentliche News. Chance = Nachbar weg / Job = Personalnot / Neu = Sofort-Bedarf.",
    }
    path = OUT / f"{report['date']}-market.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Market: {len(hits)} -> {path}")
    for h in hits[:10]:
        print(f"  [{h['kind']}] {h['title'][:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

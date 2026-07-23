# -*- coding: utf-8 -*-
"""Lokale Nachrichten / Öffnungen scannen (RSS), Chancen für Webschmiede markieren.

Keine bezahlte API. Nur öffentliche Feeds.
  python scripts/akquise_local_news.py
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "akquise" / "reports"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Kreis Euskirchen / Region – öffentliche Feeds (ohne Key)
FEEDS = [
    {
        "id": "gnews_region",
        "name": "Google News (Mechernich/Euskirchen)",
        "url": (
            "https://news.google.com/rss/search?q="
            "Mechernich%20OR%20Euskirchen%20(Er%C3%B6ffnung%20OR%20Gastronomie%20OR%20Handwerk%20OR%20Dachdecker%20OR%20Friseur)"
            "&hl=de&gl=DE&ceid=DE:de"
        ),
    },
    {
        "id": "gnews_gewerbe",
        "name": "Google News (Gewerbe Region)",
        "url": (
            "https://news.google.com/rss/search?q="
            "%22Kreis%20Euskirchen%22%20(Gesch%C3%A4ft%20OR%20Betrieb%20OR%20Er%C3%B6ffnung%20OR%20Insolvenz)"
            "&hl=de&gl=DE&ceid=DE:de"
        ),
    },
]

# Wörter, die für uns interessant sind (Neuernöffnung, Handwerk, Gastro, Digital)
OPPORTUNITY = re.compile(
    r"(eröffn|neu\s*eröffn|neues\s+geschäft|neues\s+lokal|gastronomie|restaurant|"
    r"imbiss|café|cafe|handwerk|dachdeck|elektro|friseur|praxis|gewerbe|"
    r"digital|website|online|lieferando|insolvenz|nachfolge|übernahm)",
    re.I,
)

REGION = re.compile(
    r"(mechernich|euskirchen|zülich|zuelich|kommern|nettersheim|schleiden|"
    r"bad münstereifel|muenstereifel|call|blankenheim|hellenthal)",
    re.I,
)


def fetch_feed(url: str, ua: str) -> list[dict]:
    try:
        r = requests.get(url, timeout=25, headers={"User-Agent": ua})
        r.raise_for_status()
    except requests.RequestException as exc:
        return [{"error": str(exc)[:120], "url": url}]
    items = []
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError as exc:
        return [{"error": f"XML: {exc}", "url": url}]
    # RSS 2.0
    for item in root.findall(".//item")[:40]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = (item.findtext("description") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        blob = f"{title} {desc}"
        if not title:
            continue
        score = 0
        if OPPORTUNITY.search(blob):
            score += 2
        if REGION.search(blob):
            score += 2
        if score < 2:
            continue
        items.append(
            {
                "title": title[:200],
                "link": link,
                "published": pub[:40],
                "score": score,
                "why": "Neueröffnung/Branche" if OPPORTUNITY.search(blob) else "Region",
            }
        )
    return items


def main() -> int:
    ua = "Webschmiede-Akquise-News/1.0 (+https://digitalehandwerkskunst.de)"
    all_hits: list[dict] = []
    for feed in FEEDS:
        rows = fetch_feed(feed["url"], ua)
        for row in rows:
            if row.get("error"):
                print(f"FEED ERR {feed['id']}: {row['error']}")
                continue
            row["source"] = feed["name"]
            all_hits.append(row)
    all_hits.sort(key=lambda x: (-x.get("score", 0), x.get("title", "")))
    report = {
        "date": date.today().isoformat(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "center": "Mechernich / Kreis Euskirchen",
        "total": len(all_hits),
        "items": all_hits[:50],
        "note": "Öffentliche RSS. Kein Auto-Kontakt. Christian prüft und gibt frei.",
    }
    path = OUT_DIR / f"{report['date']}-local-news.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Local news: {len(all_hits)} Treffer -> {path}")
    for it in all_hits[:8]:
        print(f"  [{it.get('score')}] {it.get('title','')[:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

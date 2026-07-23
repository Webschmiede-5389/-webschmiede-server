# -*- coding: utf-8 -*-
"""Öffentliche Auftrags-/Pinnwand-Quellen (leicht).

Aktuell: Auftragsbank Region. nebenan.de = nur Watch-Link (Login-Wall).
"""
from __future__ import annotations

import hashlib
import re
import time
from typing import Any
from urllib.parse import quote

import requests

UA = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; Webschmiede-Akquise/1.1; "
        "+https://digitalehandwerkskunst.de; research)"
    ),
    "Accept-Language": "de-DE,de;q=0.9",
}

# Region-Seiten Auftragsbank (IDs aus deren URL-Schema)
REGION_PAGES = [
    ("Euskirchen", "https://www.auftragsbank.de/suche-in/euskirchen/122340"),
    ("Köln", "https://www.auftragsbank.de/suche-in/koeln/122278"),
]

DEMAND = re.compile(
    r"(gesucht|suche|website|homepage|webdesign|digital|online|gastro|"
    r"handwerk|dach|elektro|maler|sanitär|friseur|auftrag)",
    re.I,
)


def fetch_auftragsbank(url: str) -> list[dict[str, Any]]:
    try:
        r = requests.get(url, timeout=28, headers=UA)
        r.raise_for_status()
    except requests.RequestException as exc:
        return [{"error": str(exc)[:120], "url": url}]

    hits = []
    for m in re.finditer(
        r'href="(https://www\.auftragsbank\.de/(?:auftraege|gesuche)/([^"]+))/?"[^>]*>',
        r.text,
        re.I,
    ):
        link = m.group(1)
        slug = re.sub(r"/\d+$", "", m.group(2))
        title = re.sub(r"\s+", " ", slug.replace("-", " ")).strip()[:160]
        if len(title) < 8:
            continue
        if not DEMAND.search(title):
            continue
        hits.append({"title": title, "link": link, "source": "auftragsbank"})
    # Dedup
    seen = set()
    out = []
    for h in hits:
        if h["link"] in seen:
            continue
        seen.add(h["link"])
        out.append(h)
    return out[:40]


def forum_watch_urls() -> list[dict[str, str]]:
    return [
        {
            "portal": "nebenan.de",
            "label": "Nachbarschaft Mechernich/Euskirchen",
            "url": "https://nebenan.de/",
            "hint": "Login nötig. Manuell nach Handwerker/Website-Gesuchen schauen.",
        },
        {
            "portal": "MyHammer",
            "label": "Aufträge Website/IT",
            "url": "https://www.myhammer.de/auftrag-finden",
            "hint": "Als Anbieter Region Eifel/NRW",
        },
        {
            "portal": "Auftragsbank",
            "label": "Kreis Euskirchen",
            "url": "https://www.auftragsbank.de/suche-in/euskirchen/122340",
            "hint": "Gesuche + Aufträge öffentlich",
        },
        {
            "portal": "Quoka",
            "label": "Kleinanzeigen alternativ",
            "url": "https://www.quoka.de/",
            "hint": "Älteres Brett, manchmal Gesuche",
        },
    ]


def scan_forums(*, pause_s: float = 1.0) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    for region, url in REGION_PAGES:
        rows = fetch_auftragsbank(url)
        time.sleep(pause_s)
        for row in rows:
            if row.get("error"):
                continue
            key = hashlib.sha1(row["link"].encode()).hexdigest()[:16]
            if key in seen:
                continue
            seen.add(key)
            title = row["title"]
            intent = "website"
            low = title.lower()
            if any(x in low for x in ("gastro", "restaurant", "imbiss")):
                intent = "bestellportal"
            elif any(x in low for x in ("social", "instagram", "facebook")):
                intent = "social"
            elif any(x in low for x in ("buchhaltung", "edv", "it ")):
                intent = "automation"
            hits.append(
                {
                    "id": key,
                    "source": "auftragsbank",
                    "intent_id": intent,
                    "intent_label": f"Auftrag/Gesuch ({region})",
                    "title": title[:200],
                    "link": row["link"],
                    "score": 5 if "gesucht" in low else 4,
                    "why": f"Auftragsbank {region}",
                    "offer_hook": "Lokaler Auftrag/Gesuch, Add-on oder Komplett-Paket",
                }
            )
    hits.sort(key=lambda x: (-x["score"], x["title"]))
    return hits

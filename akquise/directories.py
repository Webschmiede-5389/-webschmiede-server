# -*- coding: utf-8 -*-
"""Gelbe Seiten / Branchenbuch: öffentliche Suche (leicht, limitiert).

Ergänzt OSM+Places um Betriebe, die im klassischen Branchenbuch stehen
(oft kleine Betriebe ohne starke Website).
"""
from __future__ import annotations

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

# Branche → Gelbe-Seiten-Suchbegriff
VERTICAL_QUERIES: dict[str, list[str]] = {
    "gastro": ["restaurant", "imbiss", "café"],
    "dach": ["dachdecker", "bedachung"],
    "trockenbau": ["trockenbau", "gipser"],
    "elektro": ["elektriker", "elektroinstallation"],
    "handwerk": ["sanitär", "maler", "schreiner"],
    "friseur": ["friseur"],
    "dental": ["zahnarzt"],
    "fliesenleger": ["fliesenleger", "plattenleger"],
    "gartenbau": ["gartenbau", "landschaftsbau"],
    "hochbau": ["maurer", "hochbau", "bauunternehmen"],
    "tiefbau": ["tiefbau", "straßenbau", "kanalbau"],
}


def _search_url(what: str, where: str) -> str:
    return f"https://www.gelbeseiten.de/suche/{quote(what)}/{quote(where)}"


def fetch_listings(what: str, where: str, *, timeout: int = 28) -> list[dict[str, Any]]:
    url = _search_url(what, where)
    try:
        r = requests.get(url, timeout=timeout, headers=UA)
        r.raise_for_status()
    except requests.RequestException as exc:
        return [{"error": str(exc)[:120], "url": url}]

    html = r.text
    names = re.findall(r'class="mod-Treffer__name"[^>]*>\s*([^<]+)\s*<', html)
    # Telefon oft in data-Attributen oder tel:-Links
    phones = re.findall(r'href="tel:([^"]+)"', html)
    websites = re.findall(r'data-wipe-url="(https?://[^"]+)"', html)
    if not websites:
        websites = re.findall(r'rel="noopener"[^>]*href="(https?://(?!www\.gelbeseiten)[^"]+)"', html)

    out: list[dict[str, Any]] = []
    for i, name in enumerate(names):
        name = re.sub(r"\s+", " ", name).strip()
        if len(name) < 2:
            continue
        phone = phones[i] if i < len(phones) else ""
        web = websites[i] if i < len(websites) else ""
        out.append(
            {
                "name": name,
                "phone": phone.replace(" ", ""),
                "website": web,
                "source": "gelbeseiten",
                "query": what,
                "city": where,
                "directory_url": url,
            }
        )
    # Dedup
    seen: set[str] = set()
    uniq = []
    for row in out:
        key = row["name"].lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(row)
    return uniq[:40]


def enrich_from_directories(
    leads: list[dict],
    vertical_id: str,
    cities: list[str],
    *,
    pause_s: float = 1.1,
) -> int:
    """Neue Leads aus Gelbe Seiten mergen (Name-Dedup)."""
    queries = VERTICAL_QUERIES.get(vertical_id) or [vertical_id]
    existing = {((l.get("name") or "").strip().lower()) for l in leads}
    added = 0
    for city in cities:
        for what in queries[:2]:
            rows = fetch_listings(what, city)
            time.sleep(pause_s)
            for row in rows:
                if row.get("error"):
                    continue
                key = row["name"].lower()
                if key in existing:
                    # Telefon/Website nachziehen wenn leer
                    for lead in leads:
                        if (lead.get("name") or "").strip().lower() == key:
                            if row.get("phone") and not lead.get("phone"):
                                lead["phone"] = row["phone"]
                            if row.get("website") and not lead.get("website"):
                                lead["website"] = row["website"]
                            lead.setdefault("directory_hits", []).append("gelbeseiten")
                            break
                    continue
                existing.add(key)
                leads.append(
                    {
                        "name": row["name"],
                        "amenity": what,
                        "cuisine": "",
                        "description": "Gelbe Seiten",
                        "address": city,
                        "phone": row.get("phone") or "",
                        "website": row.get("website") or "",
                        "email": "",
                        "lat": 0.0,
                        "lon": 0.0,
                        "osm_id": None,
                        "google_places": {},
                        "signals": {},
                        "score": 0,
                        "priority": "low",
                        "pitch_angle": "",
                        "pitch_angles": [],
                        "directory_hits": ["gelbeseiten"],
                        "discovery_center": city,
                    }
                )
                added += 1
    return added

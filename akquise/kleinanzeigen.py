# -*- coding: utf-8 -*-
"""Kleinanzeigen-Suche (öffentliche HTML-Ergebnisse, höflich, limitiert).

Kein Login, keine Massen-Requests. Nur B2B-Nachfrage-Queries.
Christian hat Freigabe für diesen leichten Scan (Juli 2026).
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
    "Accept": "text/html,application/xhtml+xml",
}

# Suchbegriffe = Nachfrage (Gesuche + Angebote die Hilfe brauchen)
SEARCHES: list[dict[str, str]] = [
    {"id": "website", "q": "website-gesucht", "label": "Website gesucht"},
    {"id": "website", "q": "homepage-gesucht", "label": "Homepage gesucht"},
    {"id": "website", "q": "webdesigner-gesucht", "label": "Webdesigner gesucht"},
    {"id": "bestellportal", "q": "bestellsystem-gesucht", "label": "Bestellsystem gesucht"},
    {"id": "automation", "q": "buchhaltung-hilfe-gesucht", "label": "Buchhaltung Hilfe"},
    {"id": "pc_buero", "q": "edv-hilfe-gesucht", "label": "EDV Hilfe gesucht"},
    {"id": "social", "q": "social-media-manager-gesucht", "label": "Social Media gesucht"},
]

REGION_HINT = re.compile(
    r"(euskirchen|mechernich|eifel|zülich|zuelich|kommern|schleiden|"
    r"münstereifel|muenstereifel|nrw|köln|koeln|bonn|düüren|dueren|"
    r"rhein.?erft|kerpen|bergheim|weilerswist|swisttal)",
    re.I,
)
B2B_HINT = re.compile(
    r"(firma|betrieb|gmbh|restaurant|imbiss|handwerk|gewerbe|laden|"
    r"praxis|website|homepage|webdesign|bestell|buchhaltung|social|"
    r"edv|it.?hilfe|automat)",
    re.I,
)
PRIVATE_SKIP = re.compile(
    r"(hochzeit|privatunterricht|nachhilfe mathe|baby|kinderwagen)",
    re.I,
)
SUPPLY_SKIP = re.compile(
    r"(erstelle(n)?\s+(f.r)|webdesign ab|nur\s+\d+\s*[€,]|profi html|"
    r"shopify shop|seo\s*\||2.?7\s*tage|custom code|wir erstellen|"
    r"unsere leistung|professionelle (shopify|homepage|website) erstellen|"
    r"webseite f.r nur|ab 399)",
    re.I,
)


def _search_url(slug: str) -> str:
    return f"https://www.kleinanzeigen.de/s-{quote(slug)}/k0"


def fetch_search(slug: str, *, timeout: int = 28) -> list[dict[str, Any]]:
    url = _search_url(slug)
    try:
        r = requests.get(url, timeout=timeout, headers=UA)
        r.raise_for_status()
    except requests.RequestException as exc:
        return [{"error": str(exc)[:120], "url": url}]

    html = r.text
    # Ad cards: href + title nearby
    items: list[dict[str, Any]] = []
    for m in re.finditer(
        r'href="(/s-anzeige/[^"]+)"[^>]*>\s*(?:<[^>]+>\s*)*([^<]{8,140})',
        html,
        re.I,
    ):
        path, title = m.group(1), re.sub(r"\s+", " ", m.group(2)).strip()
        if not title or title.lower() in ("anzeige", "mehr"):
            continue
        items.append(
            {
                "title": title[:180],
                "link": "https://www.kleinanzeigen.de" + path.split("?")[0],
                "url_search": url,
            }
        )

    # Fallback: ellipsis titles
    if len(items) < 3:
        titles = re.findall(r'class="[^"]*ellipsis[^"]*"[^>]*>([^<]{8,140})<', html)
        links = re.findall(r'href="(/s-anzeige/[^"]+)"', html)
        for i, title in enumerate(titles[:25]):
            link = links[i] if i < len(links) else ""
            items.append(
                {
                    "title": re.sub(r"\s+", " ", title).strip()[:180],
                    "link": ("https://www.kleinanzeigen.de" + link.split("?")[0]) if link else url,
                    "url_search": url,
                }
            )

    # Dedup
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for it in items:
        key = it["title"].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out[:30]


def score_ad(title: str) -> tuple[int, str]:
    if PRIVATE_SKIP.search(title):
        return 0, "privat"
    if SUPPLY_SKIP.search(title):
        return 0, "Anbieter-Anzeige"
    # Nur echte Nachfrage, sonst zu viele Agentur-Angebote
    demand = re.search(
        r"(gesucht|suche\b|brauche|benötige|benoetige|wer macht|wer kann|"
        r"hilfe gesucht|auftraggeber|firma sucht)",
        title,
        re.I,
    )
    if not demand:
        return 0, "kein Gesuch"
    if not B2B_HINT.search(title):
        return 0, "kein B2B"
    score = 4
    why = ["Gesuch", "B2B"]
    if REGION_HINT.search(title):
        score += 3
        why.append("Region")
    return score, ", ".join(why)


def scan_kleinanzeigen(*, pause_s: float = 1.2) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    for spec in SEARCHES:
        rows = fetch_search(spec["q"])
        time.sleep(pause_s)
        for row in rows:
            if row.get("error"):
                continue
            title = row.get("title") or ""
            sc, why = score_ad(title)
            if sc < 2:
                continue
            key = hashlib.sha1(f"{title}|{row.get('link','')}".encode()).hexdigest()[:16]
            if key in seen:
                continue
            seen.add(key)
            hits.append(
                {
                    "id": key,
                    "source": "kleinanzeigen",
                    "intent_id": spec["id"],
                    "intent_label": spec["label"],
                    "title": title,
                    "link": row.get("link") or "",
                    "score": sc,
                    "why": why,
                    "offer_hook": _hook(spec["id"]),
                }
            )
    hits.sort(key=lambda x: (-x["score"], x["title"]))
    return hits


def _hook(intent_id: str) -> str:
    return {
        "website": "Website + Maps, Add-on ohne Systemwechsel",
        "bestellportal": "Eigenes Bestellportal neben Lieferando",
        "automation": "n8n / Prozesse / Buchhaltung digital",
        "pc_buero": "Erst sichtbar, dann Automation",
        "social": "Content + Funnel, Ads optional",
    }.get(intent_id, "Webschmiede Add-on")

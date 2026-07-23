# -*- coding: utf-8 -*-
"""Quoka leichter HTML-Scan (Verticals).

Öffentliche Such-/Kategorie-Seiten. Kein Login, Pause zwischen Requests.
Filter: echte Nachfrage, Anbieter-Spam raus.
"""
from __future__ import annotations

import hashlib
import re
import time
from typing import Any
import requests

UA = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; Webschmiede-Akquise/1.1; "
        "+https://digitalehandwerkskunst.de; research)"
    ),
    "Accept-Language": "de-DE,de;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
}

AD_RE = re.compile(
    r'href="(https://www\.quoka\.de/anzeigen/[^"]+/anzeige/([^/]+)/[^"]+\.html)"',
    re.I,
)

VERTICAL_SEARCHES: dict[str, list[dict[str, str]]] = {
    "gastro": [
        {"q": "restaurant+nachfolger", "label": "Gastro Nachfolge"},
        {"q": "imbiss+abzugeben", "label": "Imbiss abzugeben"},
        {"q": "gastronomie+website", "label": "Gastro Website"},
        {"q": "restaurant+homepage+gesucht", "label": "Restaurant Homepage"},
    ],
    "handwerk": [
        {"q": "handwerker+gesucht", "label": "Handwerker gesucht"},
        {"q": "dachdecker+gesucht", "label": "Dachdecker gesucht"},
        {"q": "betrieb+abzugeben+handwerk", "label": "Handwerk abgeben"},
        {"q": "website+handwerk+gesucht", "label": "Handwerk Website"},
    ],
    "friseur": [
        {"q": "friseur+nachfolge", "label": "Friseur Nachfolge"},
        {"q": "friseursalon+abzugeben", "label": "Salon abzugeben"},
        {"q": "friseur+website+gesucht", "label": "Friseur Website"},
    ],
    "dach": [
        {"q": "dachdecker+gesucht", "label": "Dachdecker gesucht"},
        {"q": "dachdeckerei+abzugeben", "label": "Dachdeckerei abgeben"},
        {"q": "dachdecker+nachfolge", "label": "Dach Nachfolge"},
        {"q": "dachdecker+website", "label": "Dach Website"},
    ],
    "elektro": [
        {"q": "elektriker+gesucht", "label": "Elektriker gesucht"},
        {"q": "elektro+betrieb+abzugeben", "label": "Elektro abgeben"},
        {"q": "elektro+nachfolge", "label": "Elektro Nachfolge"},
        {"q": "elektro+website+gesucht", "label": "Elektro Website"},
    ],
    "trockenbau": [
        {"q": "trockenbau+gesucht", "label": "Trockenbau gesucht"},
        {"q": "trockenbau+nachfolge", "label": "Trockenbau Nachfolge"},
        {"q": "trockenbau+abzugeben", "label": "Trockenbau abgeben"},
        {"q": "gipser+gesucht", "label": "Gipser gesucht"},
    ],
    "fliesenleger": [
        {"q": "fliesenleger+gesucht", "label": "Fliesenleger gesucht"},
        {"q": "fliesenleger+nachfolge", "label": "Fliesen Nachfolge"},
        {"q": "fliesenleger+abzugeben", "label": "Fliesenbetrieb abgeben"},
        {"q": "plattenleger+gesucht", "label": "Plattenleger gesucht"},
    ],
    "gartenbau": [
        {"q": "gartenbauer+gesucht", "label": "Gartenbauer gesucht"},
        {"q": "gartenbau+nachfolge", "label": "Gartenbau Nachfolge"},
        {"q": "landschaftsbau+abzugeben", "label": "Galabau abgeben"},
        {"q": "galabau+website", "label": "Galabau Website"},
    ],
    "hochbau": [
        {"q": "maurer+gesucht", "label": "Maurer gesucht"},
        {"q": "hochbau+nachfolge", "label": "Hochbau Nachfolge"},
        {"q": "bauunternehmen+abzugeben", "label": "Bauunternehmen abgeben"},
        {"q": "betonbauer+gesucht", "label": "Betonbauer gesucht"},
    ],
    "tiefbau": [
        {"q": "tiefbau+gesucht", "label": "Tiefbau gesucht"},
        {"q": "tiefbau+nachfolge", "label": "Tiefbau Nachfolge"},
        {"q": "straßenbau+abzugeben", "label": "Straßenbau abgeben"},
        {"q": "kanalbau+gesucht", "label": "Kanalbau gesucht"},
    ],
}

CATEGORY_PAGES = [
    (
        "auftragsgesuche",
        "https://www.quoka.de/anzeigen/jobs-business/stellenmarkt/auftragsgesuche-gewerblich/",
    ),
    (
        "nrw-jobs",
        "https://www.quoka.de/anzeigen/jobs-business/nordrhein-westfalen/",
    ),
    (
        "koeln-jobs",
        "https://www.quoka.de/anzeigen/jobs-business/koeln/",
    ),
]

REGION_HINT = re.compile(
    r"(euskirchen|mechernich|eifel|zülich|zuelich|kommern|schleiden|"
    r"münstereifel|muenstereifel|nrw|köln|koeln|bonn|düüren|dueren|"
    r"rhein.?erft|kerpen|bergheim|weilerswist|swisttal|dortmund|"
    r"essen|düsseldorf|duesseldorf|aachen)",
    re.I,
)
DEMAND = re.compile(
    r"(gesucht|suche\b|brauche|benötige|benoetige|nachfolge|abzugeben|"
    r"übernahme|uebernahme|wer macht|hilfe|auftrag)",
    re.I,
)
B2B = re.compile(
    r"(firma|betrieb|gmbh|restaurant|imbiss|gastro|handwerk|gewerbe|"
    r"laden|praxis|friseur|salon|dach|elektro|website|homepage|"
    r"webdesign|büro|buero|social|edv|it\b|nachfolger)",
    re.I,
)
SUPPLY_SKIP = re.compile(
    r"(ich (biete|erstelle|übernehme|uebernehme)|wir (bieten|erstellen)|"
    r"ghostwriter|texter schreibt|virtuelle (assistenz|hilfe)|"
    r"pflegevermittlung|24h.?7|haushaltshilfe|zusatzverdienst)",
    re.I,
)
NOISE = re.compile(
    r"(katze|hund|pferd|ferienhaus|ferienwohnung|hausboot|erotik|"
    r"partnerschaft|bekanntschaft)",
    re.I,
)


def _title_from_slug(slug: str) -> str:
    return re.sub(r"\s+", " ", slug.replace("-", " ")).strip()[:160]


def fetch_ads(url: str) -> list[dict[str, str]]:
    try:
        r = requests.get(url, timeout=28, headers=UA)
        r.raise_for_status()
    except requests.RequestException as exc:
        return [{"error": str(exc)[:120], "url": url}]

    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for link, slug in AD_RE.findall(r.text):
        if link in seen:
            continue
        seen.add(link)
        out.append(
            {
                "title": _title_from_slug(slug),
                "link": link.split("?")[0],
                "url_search": url,
            }
        )
    return out[:40]


def score_ad(title: str, *, vertical: str) -> tuple[int, str]:
    if NOISE.search(title):
        return 0, "noise"
    if SUPPLY_SKIP.search(title):
        return 0, "Anbieter"
    if not DEMAND.search(title):
        return 0, "kein Gesuch"
    if not B2B.search(title):
        return 0, "kein B2B"

    score = 3
    why = ["Gesuch", "B2B"]
    low = title.lower()
    vert_kw = {
        "gastro": ("gastro", "restaurant", "imbiss", "café", "cafe", "kneipe"),
        "handwerk": (
            "handwerk",
            "dach",
            "elektro",
            "maler",
            "sanitär",
            "sanitaer",
            "bau",
            "betrieb",
        ),
        "friseur": ("friseur", "salon", "barber", "haar", "beauty"),
        "dach": ("dach", "dachdecker", "zimmerei", "steildach", "flachdach"),
        "elektro": ("elektro", "elektriker", "elektrotechnik", "installation"),
        "trockenbau": ("trockenbau", "gipser", "stuckateur", "innenausbau", "verputz"),
        "fliesenleger": ("fliesen", "plattenleger", "mosaik"),
        "gartenbau": ("gartenbau", "landschaft", "galabau", "gartenpflege"),
        "hochbau": ("hochbau", "maurer", "betonbau", "rohbau", "bauunternehmen"),
        "tiefbau": ("tiefbau", "straßenbau", "strassenbau", "kanalbau", "erdbau"),
    }.get(vertical, ())
    if any(k in low for k in vert_kw):
        score += 2
        why.append(vertical)
    if REGION_HINT.search(title):
        score += 2
        why.append("Region")
    if re.search(r"(nachfolge|abzugeben|übernahme|uebernahme)", title, re.I):
        score += 2
        why.append("Nachfolge")
    return score, ", ".join(why)


def _hook(vertical: str) -> str:
    return {
        "gastro": "Bestellportal / Website, Lieferando bleibt optional",
        "handwerk": "Website + Anfragen, Add-on ohne Systemwechsel",
        "friseur": "Termin + Auftritt, Nachfolge = neuer digitaler Start",
        "dach": "Website + Anfragen, Nachfolge = neuer Auftritt",
        "elektro": "Website + Anfragen, Nachfolge = neuer Auftritt",
        "trockenbau": "Website + Anfragen, Vorher/Nachher sichtbar",
        "fliesenleger": "Website + Anfragen, Referenzfotos",
        "gartenbau": "Website + Anfragen, Saison-Leads",
        "hochbau": "Website + Anfragen, Projekte zeigen",
        "tiefbau": "Website + Anfragen, Maschinen/Referenzen",
    }.get(vertical, "Webschmiede Add-on")


def scan_quoka(
    *,
    verticals: list[str] | None = None,
    pause_s: float = 1.0,
    include_categories: bool = True,
) -> list[dict[str, Any]]:
    verts = verticals or list(VERTICAL_SEARCHES.keys())
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()

    for vid in verts:
        specs = VERTICAL_SEARCHES.get(vid) or []
        for spec in specs:
            url = f"https://www.quoka.de/anzeigen/?q={spec['q']}"
            rows = fetch_ads(url)
            time.sleep(pause_s)
            for row in rows:
                if row.get("error"):
                    continue
                title = row.get("title") or ""
                sc, why = score_ad(title, vertical=vid)
                if sc < 3:
                    continue
                key = hashlib.sha1(f"{title}|{row.get('link','')}".encode()).hexdigest()[
                    :16
                ]
                if key in seen:
                    continue
                seen.add(key)
                hits.append(
                    {
                        "id": key,
                        "source": "quoka",
                        "vertical": vid,
                        "intent_id": "website",
                        "intent_label": spec["label"],
                        "title": title,
                        "link": row.get("link") or "",
                        "score": sc,
                        "why": why,
                        "offer_hook": _hook(vid),
                    }
                )

    if include_categories:
        for cat_id, url in CATEGORY_PAGES:
            rows = fetch_ads(url)
            time.sleep(pause_s)
            for row in rows:
                if row.get("error"):
                    continue
                title = row.get("title") or ""
                # Kategorie: Vertical anhand Keywords
                vid = "handwerk"
                low = title.lower()
                if any(k in low for k in ("gastro", "restaurant", "imbiss")):
                    vid = "gastro"
                elif any(k in low for k in ("friseur", "salon", "beauty")):
                    vid = "friseur"
                elif any(k in low for k in ("dach", "dachdecker", "zimmerei")):
                    vid = "dach"
                elif any(k in low for k in ("elektro", "elektriker")):
                    vid = "elektro"
                elif any(k in low for k in ("trockenbau", "gipser", "stuckateur")):
                    vid = "trockenbau"
                elif any(k in low for k in ("fliesen", "plattenleger")):
                    vid = "fliesenleger"
                elif any(k in low for k in ("gartenbau", "landschaft", "galabau")):
                    vid = "gartenbau"
                elif any(k in low for k in ("hochbau", "maurer", "betonbau", "rohbau")):
                    vid = "hochbau"
                elif any(k in low for k in ("tiefbau", "straßenbau", "strassenbau", "kanalbau")):
                    vid = "tiefbau"
                if vid not in verts:
                    continue
                sc, why = score_ad(title, vertical=vid)
                if sc < 4:
                    continue
                key = hashlib.sha1(f"{title}|{row.get('link','')}".encode()).hexdigest()[
                    :16
                ]
                if key in seen:
                    continue
                seen.add(key)
                hits.append(
                    {
                        "id": key,
                        "source": "quoka",
                        "vertical": vid,
                        "intent_id": "website",
                        "intent_label": f"Quoka {cat_id}",
                        "title": title,
                        "link": row.get("link") or "",
                        "score": sc,
                        "why": f"{why}, {cat_id}",
                        "offer_hook": _hook(vid),
                    }
                )

    hits.sort(key=lambda x: (-x["score"], x["title"]))
    return hits


def quoka_watch_urls() -> list[dict[str, str]]:
    return [
        {
            "portal": "Quoka",
            "label": "Auftragsgesuche gewerblich",
            "url": CATEGORY_PAGES[0][1],
            "hint": "Weniger Konkurrenz als Kleinanzeigen",
        },
        {
            "portal": "Quoka",
            "label": "Jobs/Business NRW",
            "url": CATEGORY_PAGES[1][1],
            "hint": "Region NRW",
        },
        {
            "portal": "Quoka",
            "label": "Jobs/Business Köln",
            "url": CATEGORY_PAGES[2][1],
            "hint": "Nähe Eifel/Rheinland",
        },
    ]

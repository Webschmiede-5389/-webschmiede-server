# -*- coding: utf-8 -*-
"""nexxt-change Unternehmensbörse (öffentliche Verkaufsangebote).

Nachfolge = heißer Intent (neuer digitaler Auftritt).
Form-POST wie Browser, höflich, limitiert.
"""
from __future__ import annotations

import hashlib
import html as html_lib
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

FORM_URL = (
    "https://www.nexxt-change.org/SiteGlobals/Forms/"
    "Verkaufsangebot_Suche/Verkaufsangebotssuche_Formular"
)

# NACE-Codes aus der nexxt-change Branchenliste
NACE: dict[str, str] = {
    "handwerk": "[13]",
    "gastro": "[4,24]",
    "friseur": "[3,22,127]",
    "dach": "[13,66,229]",
    "elektro": "[13,67,241]",
    "trockenbau": "[1,14,60]",
    "fliesenleger": "[13,67,245]",
    "gartenbau": "[3,22,128]",
    "hochbau": "[13,66,227]",
    "tiefbau": "[13,66,230]",
}

# NUTS: Köln-Regierungsbezirk (inkl. Euskirchen) + ganz NRW Fallback
NUTS_KOELN = "[10,27]"
NUTS_NRW = "[10]"

TITLE_RE = re.compile(
    r'Detailseite/detailseite_jsp\?adId=(\d+)[^"]*"[^>]*>([^<]{5,200})</a>',
    re.I,
)
DETAIL_RE = re.compile(
    r'href="(https://www\.nexxt-change\.org/DE/Verkaufsangebot/'
    r'Detailseite/[^"]+adId=(\d+)[^"]*)"',
    re.I,
)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(text or "")).strip()[:200]


def _hidden_fields(html: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, val in re.findall(
        r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"',
        html,
        re.I,
    ):
        out[name] = val
    for name, val in re.findall(
        r'<input[^>]*name="([^"]+)"[^>]*type="hidden"[^>]*value="([^"]*)"',
        html,
        re.I,
    ):
        out.setdefault(name, val)
    return out


def _parse_results(html: str) -> list[dict[str, str]]:
    titles = {aid: _clean(title) for aid, title in TITLE_RE.findall(html)}
    seen: set[str] = set()
    rows: list[dict[str, str]] = []
    for link, aid in DETAIL_RE.findall(html):
        if aid in seen:
            continue
        seen.add(aid)
        title = titles.get(aid) or f"Nachfolge-Inserat {aid}"
        rows.append(
            {
                "id": aid,
                "title": title,
                "link": link.split("&amp;")[0].replace("&amp;", "&"),
            }
        )
    return rows[:30]


def fetch_vertical(
    vertical: str,
    *,
    session: requests.Session | None = None,
    nuts: str = NUTS_KOELN,
) -> list[dict[str, str]]:
    nace = NACE.get(vertical)
    if not nace:
        return []
    s = session or requests.Session()
    s.headers.update(UA)
    try:
        r0 = s.get(FORM_URL, timeout=30)
        r0.raise_for_status()
    except requests.RequestException as exc:
        return [{"error": str(exc)[:120]}]

    payload = _hidden_fields(r0.text)
    payload.update(
        {
            "suchbegriff": "",
            "ad_nace": nace,
            "ad_nace.GROUP": "1",
            "ad_nuts": nuts,
            "ad_nuts.GROUP": "1",
            "ad_zip": "",
            "ad_radius": "",
        }
    )
    try:
        r1 = s.post(FORM_URL, data=payload, timeout=40, allow_redirects=True)
        r1.raise_for_status()
    except requests.RequestException as exc:
        return [{"error": str(exc)[:120]}]

    rows = _parse_results(r1.text)
    # Fallback NRW wenn Köln leer
    if len(rows) < 2 and nuts != NUTS_NRW:
        time.sleep(0.8)
        return fetch_vertical(vertical, session=s, nuts=NUTS_NRW)
    return rows


def _hook(vertical: str) -> str:
    return {
        "gastro": "Nachfolge Gastro: Website + Bestellportal als Startpaket",
        "handwerk": "Nachfolge Handwerk: neuer Auftritt, Anfragen digital",
        "friseur": "Salon-Nachfolge: Termin + Website neu",
        "dach": "Dach-Nachfolge: Website + Anfragen",
        "elektro": "Elektro-Nachfolge: Website + Anfragen",
        "trockenbau": "Trockenbau-Nachfolge: Auftritt + Anfragen",
        "fliesenleger": "Fliesen-Nachfolge: Auftritt + Referenzen",
        "gartenbau": "Galabau-Nachfolge: Auftritt + Saison-Leads",
        "hochbau": "Hochbau-Nachfolge: Auftritt + Projekte",
        "tiefbau": "Tiefbau-Nachfolge: Auftritt + Referenzen",
    }.get(vertical, "Nachfolge = neuer digitaler Start")


def scan_nexxt(
    *,
    verticals: list[str] | None = None,
    pause_s: float = 1.0,
) -> list[dict[str, Any]]:
    verts = verticals or list(NACE.keys())
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    session = requests.Session()
    session.headers.update(UA)

    for vid in verts:
        if vid not in NACE:
            continue
        rows = fetch_vertical(vid, session=session, nuts=NUTS_KOELN)
        time.sleep(pause_s)
        for row in rows:
            if row.get("error"):
                continue
            title = row.get("title") or ""
            link = row.get("link") or ""
            aid = row.get("id") or ""
            key = hashlib.sha1(f"nexxt|{aid}|{title}".encode()).hexdigest()[:16]
            if key in seen:
                continue
            seen.add(key)
            score = 6
            why = ["Nachfolge", "nexxt-change"]
            low = title.lower()
            if any(x in low for x in ("euskirchen", "mechernich", "eifel", "köln", "koeln", "bonn", "düüren", "dueren")):
                score += 2
                why.append("Region eng")
            hits.append(
                {
                    "id": key,
                    "source": "nexxt",
                    "vertical": vid,
                    "intent_id": "website",
                    "intent_label": f"Nachfolge {vid}",
                    "title": title,
                    "link": link,
                    "score": score,
                    "why": ", ".join(why),
                    "offer_hook": _hook(vid),
                }
            )

    hits.sort(key=lambda x: (-x["score"], x["title"]))
    return hits


def nexxt_watch_urls() -> list[dict[str, str]]:
    return [
        {
            "portal": "nexxt-change",
            "label": "Verkaufsangebote (Nachfolge)",
            "url": "https://www.nexxt-change.org/DE/Verkaufsangebot/inhalt",
            "hint": "Offizielle Börse, Filter Branche + Köln/NRW",
        },
        {
            "portal": "nexxt-change",
            "label": "Suchformular",
            "url": FORM_URL,
            "hint": "Handwerk / Gastro / Friseur / Dach / Elektro",
        },
    ]

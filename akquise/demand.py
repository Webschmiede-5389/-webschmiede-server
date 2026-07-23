# -*- coding: utf-8 -*-
"""Reverse-Akquise: Betriebe die aktiv Hilfe suchen (Website, Portal, Automation, …).

Quellen:
  - Google News RSS mit Intent-Queries + Region
  - Kleinanzeigen (leichter öffentlicher Such-Scan, freigegeben)
  - Watch-Links MyHammer/Twago

Kein Auto-Kontakt. Christian gibt frei vor Anruf.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "akquise" / "reports"
SETTINGS = ROOT / "akquise" / "settings.json"

# Branchen für Quoka / nexxt / Dark-Watch (Bau + Bestand)
DARK_VERTICALS = [
    "gastro",
    "handwerk",
    "friseur",
    "dach",
    "elektro",
    "trockenbau",
    "fliesenleger",
    "gartenbau",
    "hochbau",
    "tiefbau",
]

# Was Kunden typischerweise suchen (B2B-Nachfrage)
INTENTS: list[dict[str, Any]] = [
    {
        "id": "website",
        "label": "Website / Homepage gesucht",
        "queries": [
            "Website erstellen lassen",
            "Homepage erstellen lassen",
            "Webseite machen lassen",
            "suche Webdesigner",
            "brauche eine Website",
        ],
        "offer_hook": "Website + Google Maps, Paket Starter/Standard",
    },
    {
        "id": "bestellportal",
        "label": "Bestellseite / Online-Bestellen",
        "queries": [
            "Online Bestellsystem Restaurant",
            "Bestellseite erstellen lassen",
            "weg von Lieferando",
            "eigene Bestellseite Imbiss",
            "Online Bestellung Abholung",
        ],
        "offer_hook": "Eigenes Bestellportal wie Snack House, 0 % Provision",
    },
    {
        "id": "automation",
        "label": "Automation / n8n / Prozesse",
        "queries": [
            "Automatisierung Betrieb gesucht",
            "Buchhaltung digitalisieren Handwerk",
            "Prozesse automatisieren Gastronomie",
            "n8n Freelancer",
            "Zapier Alternative Deutschland Handwerk",
        ],
        "offer_hook": "n8n-Workflows, CRM, SMS, Reporting",
    },
    {
        "id": "social",
        "label": "Social Media / Posts",
        "queries": [
            "Social Media Betreuung Restaurant",
            "Instagram Posts machen lassen Imbiss",
            "Facebook Werbung Handwerk Region",
        ],
        "offer_hook": "Content-Pipeline + optional Ads (Freigabe)",
    },
    {
        "id": "pc_buero",
        "label": "PC / Büro / IT vor Ort",
        "queries": [
            "EDV Hilfe Handwerksbetrieb",
            "Computer Hilfe Firma Euskirchen",
            "IT Betreuung kleinbetrieb",
        ],
        "offer_hook": "Erst digital sichtbar machen, dann Automation",
    },
    {
        "id": "lieferando_pain",
        "label": "Lieferando / Provision ärgert",
        "queries": [
            "Lieferando Provision zu hoch",
            "Lieferando Alternative eigenes System",
            "ohne Lieferando bestellen",
        ],
        "offer_hook": "ROI: Provision sparen durch eigenes Portal",
    },
]

# Muss im Titel/Text vorkommen, sonst nur Region-News
INTENT_MUST = re.compile(
    r"(website|webseite|homepage|webdesigner|bestell(seite|system|portal)|lieferando|"
    r"online.?bestell|automatis\w*|buchhaltung\s+digital|social.?media|"
    r"instagram\s+(betreu|machen|post)|edv.?hilfe|it.?betreuung|"
    r"(website|homepage|webseite).{0,20}(erstellen|machen)\s+lassen|"
    r"(suche|gesucht).{0,30}(webdesigner|homepage|website|programmier|freelancer))",
    re.I,
)

# B2B-Filter
B2B_HINT = re.compile(
    r"(restaurant|imbiss|gastro|café|cafe|bäckerei|baeckerei|friseur|handwerk|"
    r"dachdeck|elektro|maler|sanitär|sanitaer|gmbh|ug\b|e\.?\s*k\.?|betrieb|"
    r"laden|praxis|zahn|salon|werkstatt|meister|gewerbe|firma|unternehmen|"
    r"lieferando|bestell|gastronom)",
    re.I,
)
PRIVATE_HINT = re.compile(
    r"(hochzeit|privat|geburtstag|hobby|meine tochter|student|lebenslauf|"
    r"weihnachts|festival|krimi|tesla|schule trifft|pferdehof|glühwein|gluehwein|"
    r"berufsberatung|eignungstest)",
    re.I,
)
REGION = re.compile(
    r"(mechernich|euskirchen|zülich|zuelich|kommern|nettersheim|schleiden|"
    r"bad münstereifel|muenstereifel|kreis euskirchen)",
    re.I,
)
REGION_SOFT = re.compile(r"(eifel|nrw|köln|koeln|bonn|dür(e|e)n|dueren)", re.I)


def load_center() -> dict:
    if SETTINGS.exists():
        data = json.loads(SETTINGS.read_text(encoding="utf-8"))
        return data.get("center") or {}
    return {"name": "Mechernich", "lat": 50.5997, "lon": 6.65}


def gnews_url(query: str, region_name: str) -> str:
    q = f"{query} ({region_name} OR Euskirchen OR Mechernich OR Eifel)"
    return (
        "https://news.google.com/rss/search?q="
        + quote_plus(q)
        + "&hl=de&gl=DE&ceid=DE:de"
    )


def fetch_rss(url: str, ua: str) -> list[dict]:
    try:
        r = requests.get(url, timeout=25, headers={"User-Agent": ua})
        r.raise_for_status()
    except requests.RequestException as exc:
        return [{"error": str(exc)[:120]}]
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError as exc:
        return [{"error": f"XML {exc}"}]
    out = []
    for item in root.findall(".//item")[:25]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = (item.findtext("description") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        if title:
            out.append({"title": title, "link": link, "desc": desc, "published": pub[:40]})
    return out


def score_hit(title: str, desc: str) -> tuple[int, str]:
    blob = f"{title} {desc}"
    if not INTENT_MUST.search(blob):
        return 0, "kein Intent"
    if PRIVATE_HINT.search(blob) and not B2B_HINT.search(blob):
        return 0, "privat/irrelevant"
    score = 2
    why = ["Intent"]
    if B2B_HINT.search(blob):
        score += 3
        why.append("B2B")
    if REGION.search(blob):
        score += 3
        why.append("Region eng")
    elif REGION_SOFT.search(blob):
        score += 1
        why.append("Region weit")
    return score, ", ".join(why)


def kleinanzeigen_watch_urls(center_name: str) -> list[dict]:
    """Öffentliche Such-URLs (kein Scraping). Location-Slug grob."""
    loc = "mechernich"
    # Kategorie Dienstleistungen / Computer oft 305 (kann sich ändern)
    searches = [
        ("Website erstellen", "website erstellen lassen"),
        ("Homepage", "homepage erstellen"),
        ("Online Shop / Bestellen", "bestellseite OR bestellsystem"),
        ("EDV / PC Hilfe Firma", "EDV Betreuung OR IT Hilfe Firma"),
        ("Social Media", "social media betreuung"),
        ("Buchhaltung digital", "buchhaltung digitalisieren"),
    ]
    rows = []
    for label, q in searches:
        url = (
            f"https://www.kleinanzeigen.de/s-{loc}/{quote_plus(q)}/k0l{quote_plus(loc)}"
        )
        # Stabilere Variante: reine Textsuche
        url2 = f"https://www.kleinanzeigen.de/s-{quote_plus(q)}/k0"
        rows.append(
            {
                "portal": "Kleinanzeigen",
                "label": label,
                "query": q,
                "url": url2,
                "hint": f"Filter manuell auf {center_name} / 30–50 km setzen",
            }
        )
    rows.append(
        {
            "portal": "MyHammer",
            "label": "Aufträge Website / IT",
            "query": "website",
            "url": "https://www.myhammer.de/auftrag-finden",
            "hint": "Als Anbieter registrieren, Region Eifel/NRW",
        }
    )
    rows.append(
        {
            "portal": "Twago / Freelancer",
            "label": "Projekte Website DE",
            "query": "website",
            "url": "https://www.twago.de/s/projekte/?q=website",
            "hint": "Aufträge mit Budget, oft Agentur-Konkurrenz",
        }
    )
    return rows


def scan_demand(*, max_per_intent: int = 8) -> dict:
    from kleinanzeigen import scan_kleinanzeigen

    center = load_center()
    region = center.get("name") or "Mechernich"
    ua = "Webschmiede-Akquise-Demand/1.0 (+https://digitalehandwerkskunst.de)"
    hits: list[dict] = []
    seen: set[str] = set()

    for intent in INTENTS:
        for q in intent["queries"][:3]:
            url = gnews_url(q, region)
            items = fetch_rss(url, ua)
            for it in items:
                if it.get("error"):
                    continue
                title = it.get("title") or ""
                key = hashlib.sha1(f"{title}|{it.get('link','')}".encode()).hexdigest()[:16]
                if key in seen:
                    continue
                seen.add(key)
                sc, why = score_hit(title, it.get("desc") or "")
                if sc < 3:
                    continue
                hits.append(
                    {
                        "id": key,
                        "intent_id": intent["id"],
                        "intent_label": intent["label"],
                        "offer_hook": intent["offer_hook"],
                        "query": q,
                        "title": title[:220],
                        "link": it.get("link") or "",
                        "published": it.get("published") or "",
                        "score": sc,
                        "why": why,
                        "source": "google_news",
                    }
                )

    # Kleinanzeigen (leichter HTML-Scan, freigegeben)
    try:
        for h in scan_kleinanzeigen(pause_s=1.0):
            if h["id"] in seen:
                continue
            seen.add(h["id"])
            hits.append(
                {
                    "id": h["id"],
                    "intent_id": h["intent_id"],
                    "intent_label": h.get("intent_label") or h["intent_id"],
                    "offer_hook": h.get("offer_hook") or "",
                    "query": "kleinanzeigen",
                    "title": h["title"][:220],
                    "link": h.get("link") or "",
                    "published": "",
                    "score": h.get("score") or 2,
                    "why": h.get("why") or "Kleinanzeigen",
                    "source": "kleinanzeigen",
                }
            )
    except Exception as exc:
        hits.append(
            {
                "id": "ka-error",
                "intent_id": "website",
                "intent_label": "Kleinanzeigen",
                "offer_hook": "",
                "query": "",
                "title": f"Kleinanzeigen-Scan Fehler: {exc}"[:180],
                "link": "",
                "published": "",
                "score": 0,
                "why": "error",
                "source": "kleinanzeigen",
            }
        )

    # Auftragsbank + Forum-Watch (nebenan nur manuell)
    extra_watch: list[dict] = []
    try:
        from forums import scan_forums, forum_watch_urls

        for h in scan_forums(pause_s=0.9):
            if h["id"] in seen:
                continue
            seen.add(h["id"])
            hits.append(
                {
                    "id": h["id"],
                    "intent_id": h["intent_id"],
                    "intent_label": h.get("intent_label") or h["intent_id"],
                    "offer_hook": h.get("offer_hook") or "",
                    "query": "auftragsbank",
                    "title": h["title"][:220],
                    "link": h.get("link") or "",
                    "published": "",
                    "score": h.get("score") or 4,
                    "why": h.get("why") or "Forum/Auftrag",
                    "source": h.get("source") or "auftragsbank",
                }
            )
        extra_watch = forum_watch_urls()
    except Exception as exc:
        print(f"Forums-Scan: {exc}")

    # Quoka (gastro, handwerk, friseur, dach, elektro)
    try:
        from quoka import scan_quoka, quoka_watch_urls

        for h in scan_quoka(
            verticals=DARK_VERTICALS,
            pause_s=0.9,
        ):
            if h["id"] in seen:
                continue
            seen.add(h["id"])
            hits.append(
                {
                    "id": h["id"],
                    "intent_id": h["intent_id"],
                    "intent_label": h.get("intent_label") or h["intent_id"],
                    "offer_hook": h.get("offer_hook") or "",
                    "query": f"quoka:{h.get('vertical')}",
                    "title": h["title"][:220],
                    "link": h.get("link") or "",
                    "published": "",
                    "score": h.get("score") or 3,
                    "why": h.get("why") or "Quoka",
                    "source": "quoka",
                    "vertical": h.get("vertical") or "",
                }
            )
        extra_watch.extend(quoka_watch_urls())
    except Exception as exc:
        print(f"Quoka-Scan: {exc}")

    # nexxt-change Nachfolge (heiß)
    try:
        from nexxt_change import scan_nexxt, nexxt_watch_urls

        for h in scan_nexxt(
            verticals=DARK_VERTICALS,
            pause_s=0.9,
        ):
            if h["id"] in seen:
                continue
            seen.add(h["id"])
            hits.append(
                {
                    "id": h["id"],
                    "intent_id": h["intent_id"],
                    "intent_label": h.get("intent_label") or h["intent_id"],
                    "offer_hook": h.get("offer_hook") or "",
                    "query": f"nexxt:{h.get('vertical')}",
                    "title": h["title"][:220],
                    "link": h.get("link") or "",
                    "published": "",
                    "score": h.get("score") or 6,
                    "why": h.get("why") or "nexxt-change",
                    "source": "nexxt",
                    "vertical": h.get("vertical") or "",
                }
            )
        extra_watch.extend(nexxt_watch_urls())
    except Exception as exc:
        print(f"nexxt-Scan: {exc}")

    # Dark Plurality Watch-Katalog
    try:
        from dark_sources import watch_urls as dark_watch_urls

        extra_watch.extend(dark_watch_urls(verticals=DARK_VERTICALS))
    except Exception as exc:
        print(f"Dark-Sources: {exc}")

    hits = [h for h in hits if h.get("score", 0) > 0]
    hits.sort(key=lambda x: (-x["score"], x["title"]))
    final: list[dict] = []
    per: dict[str, int] = {}
    for h in hits:
        n = per.get(h["intent_id"], 0)
        if n >= max_per_intent:
            continue
        per[h["intent_id"]] = n + 1
        final.append(h)

    ka_n = sum(1 for h in final if h.get("source") == "kleinanzeigen")
    fo_n = sum(1 for h in final if h.get("source") == "auftragsbank")
    qo_n = sum(1 for h in final if h.get("source") == "quoka")
    nx_n = sum(1 for h in final if h.get("source") == "nexxt")
    watches = kleinanzeigen_watch_urls(region)
    # Dedup watch URLs
    seen_w: set[str] = set()
    for w in extra_watch:
        u = w.get("url") or ""
        if not u or u in seen_w:
            continue
        seen_w.add(u)
        watches.append(w)
    return {
        "date": date.today().isoformat(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "center": region,
        "radius_note": "News + Kleinanzeigen + Quoka + nexxt + Auftragsbank + Dark-Watch",
        "total": len(final),
        "kleinanzeigen_hits": ka_n,
        "forum_hits": fo_n,
        "quoka_hits": qo_n,
        "nexxt_hits": nx_n,
        "hits": final,
        "watch_urls": watches,
        "note": (
            "Reverse-Akquise inkl. Dark Plurality "
            "(Quoka, nexxt-change Nachfolge, Fachquellen-Watch). "
            "nebenan.de nur Watch. Kein Auto-Kontakt."
        ),
    }


def render_html(report: dict) -> str:
    rows = ""
    for i, h in enumerate(report.get("hits") or [], 1):
        rows += (
            f"<tr><td>{i}</td><td><strong>{_e(h.get('intent_label'))}</strong>"
            f"<br><span class='muted'>{_e(h.get('offer_hook'))}</span></td>"
            f"<td>{_e(h.get('title'))}<br><a href='{_e(h.get('link'))}' target='_blank' rel='noopener'>Link</a></td>"
            f"<td>{h.get('score')}</td><td class='muted'>{_e(h.get('source'))} · {_e(h.get('why'))}</td></tr>"
        )
    watches = ""
    for w in report.get("watch_urls") or []:
        watches += (
            f"<li><strong>{_e(w.get('portal'))}</strong> · {_e(w.get('label'))}: "
            f"<a href='{_e(w.get('url'))}' target='_blank' rel='noopener'>öffnen</a> "
            f"<span class='muted'>({_e(w.get('hint'))})</span></li>"
        )
    return f"""<!DOCTYPE html>
<html lang="de"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reverse-Akquise {report.get('date')}</title>
<link href="https://fonts.bunny.net/css?family=inter:400;600;700&display=swap" rel="stylesheet">
<style>
body{{background:#0e0b08;color:#fff;font-family:Inter,sans-serif;margin:0;padding:20px;font-size:13px}}
h1{{color:#C9A84C;font-size:1.35rem}} .meta,.muted{{color:#888}}
table{{width:100%;border-collapse:collapse;margin-top:12px}} th,td{{border-bottom:1px solid #2a2a2a;padding:8px 6px;text-align:left;vertical-align:top}}
th{{color:#888}} a{{color:#C9A84C}} ul{{line-height:1.6}}
</style></head><body>
<h1>Reverse-Akquise · Nachfrage</h1>
<p class="meta">{_e(report.get('generated_at'))} · {_e(report.get('center'))} · {report.get('total')} Treffer</p>
<p class="muted">{_e(report.get('note'))}</p>
<h2 style="color:#C9A84C;font-size:1rem;margin-top:1.5rem">Portal-Watch (täglich prüfen)</h2>
<ul>{watches}</ul>
<h2 style="color:#C9A84C;font-size:1rem;margin-top:1.5rem">Gefundene Signale</h2>
<table><thead><tr><th>#</th><th>Intent</th><th>Treffer</th><th>Score</th><th>Warum</th></tr></thead>
<tbody>{rows or '<tr><td colspan="5">Keine Treffer</td></tr>'}</tbody></table>
</body></html>"""


def _e(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def save_report(report: dict) -> tuple[Path, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    j = OUT_DIR / f"{report['date']}-demand.json"
    h = OUT_DIR / f"{report['date']}-demand.html"
    j.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    h.write_text(render_html(report), encoding="utf-8")
    return j, h

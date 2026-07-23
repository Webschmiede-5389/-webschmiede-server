# -*- coding: utf-8 -*-
"""Nils Deep-Research: OpenRegister, Google Places, Crawl/Firecrawl, Web-Suche.

Sammelt belegte Quellen. Keine Halluzinationen. Ergebnis geht an Companion-LLM.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

log = logging.getLogger("nils_research")

_HERE = Path(__file__).resolve()
ROOT = _HERE.parents[2]
for cand in (_HERE.parents[1], _HERE.parents[2]):
    if (cand / "akquise").is_dir():
        ROOT = cand
        break
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)


def _env(name: str, default: str = "") -> str:
    v = (os.environ.get(name) or "").strip()
    if v:
        return v
    for base in (ROOT, ROOT / "app", Path("/root/app")):
        for fname in ("deploy.secrets.local", "requesty.secrets.local", "cursor.secrets.local"):
            p = base / fname
            if not p.is_file():
                continue
            try:
                for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                    s = line.strip()
                    if not s or s.startswith("#") or "=" not in s:
                        continue
                    k, _, val = s.partition("=")
                    if k.strip() == name:
                        return val.strip().strip('"').strip("'")
            except Exception:
                continue
    return default


def looks_like_research(text: str) -> bool:
    t = (text or "").lower()
    keys = (
        "recherch", "analysier", "schau dir", "check die firma", "untersuch",
        "finde raus", "finde info", "was weißt du über", "was weisst du über",
        "background", "firma prüfen", "firma pruefen", "konkurrenz", "markt zu",
        "openregister", "handelsregister", "places", "firecrawl", "crawl", "scrape",
        "infos zu", "info zu", "schau mal", "was kannst du zu",
    )
    if any(k in t for k in keys):
        return True
    if any(x in t for x in ("firma", "gmbh", "ug ", "unternehmen", "betrieb", "laden", "restaurant", "imbiss")) and any(
        x in t for x in ("?", "bitte", "finde", "schau", "check", "über", "ueber", "zu ")
    ):
        return True
    return False


def _firecrawl_scrape(url: str) -> dict[str, Any]:
    key = _env("FIRECRAWL_API_KEY") or _env("FIRECRAWL_KEY")
    if not key:
        return {"ok": False, "error": "no_firecrawl_key"}
    try:
        import requests

        r = requests.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"url": url, "formats": ["markdown", "links"]},
            timeout=45,
        )
        if r.status_code >= 400:
            return {"ok": False, "error": f"http_{r.status_code}", "body": r.text[:200]}
        data = r.json() if r.content else {}
        inner = data.get("data") or data
        md = (inner.get("markdown") or inner.get("content") or "")[:4000]
        title = (inner.get("metadata") or {}).get("title") if isinstance(inner.get("metadata"), dict) else ""
        return {
            "ok": True,
            "source": "firecrawl",
            "url": url,
            "title": title or "",
            "text": md,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _local_crawl(url: str) -> dict[str, Any]:
    try:
        from akquise.enrichment import crawl_website, normalize_url

        nu = normalize_url(url)
        crawled = crawl_website({"website": nu, "name": "", "url": nu}, cfg={}) or {}
        lines = [
            f"Crawl: {nu}",
            f"Titel: {crawled.get('title') or '–'}",
            f"Mail: {crawled.get('email') or '–'}",
            f"Tel: {crawled.get('phone') or '–'}",
        ]
        snippet = (crawled.get("text") or crawled.get("snippet") or "")[:800]
        if snippet:
            lines.append("Text: " + snippet)
        if crawled.get("error"):
            lines.append("Hinweis: " + str(crawled.get("error"))[:160])
        return {"ok": True, "source": "local_crawl", "url": nu, "text": "\n".join(lines), "raw": crawled}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _scrape_url(url: str) -> dict[str, Any]:
    fc = _firecrawl_scrape(url)
    if fc.get("ok"):
        return fc
    local = _local_crawl(url)
    if local.get("ok"):
        if not fc.get("ok") and fc.get("error") == "no_firecrawl_key":
            local["note"] = "Firecrawl-Key fehlt, lokaler Crawl genutzt."
        elif not fc.get("ok"):
            local["note"] = f"Firecrawl: {fc.get('error')}, Fallback lokal."
        return local
    return {"ok": False, "error": fc.get("error") or local.get("error") or "scrape_failed"}


def _places_lookup(query: str) -> dict[str, Any]:
    try:
        from akquise.places import fetch_place_details, find_place, load_api_key

        key = load_api_key()
        if not key:
            return {"ok": False, "error": "GOOGLE_PLACES_API_KEY fehlt"}
        hit = find_place(query, key)
        if not hit:
            return {"ok": False, "error": "kein Places-Treffer"}
        detail = hit
        pid = hit.get("place_id")
        if pid:
            try:
                detail = fetch_place_details(pid, key) or hit
            except Exception:
                detail = hit
        lines = [
            f"Google Places: {detail.get('name') or hit.get('name')}",
            f"Adresse: {detail.get('vicinity') or detail.get('formatted_address') or hit.get('vicinity') or '–'}",
            f"Rating: {detail.get('rating') or hit.get('rating') or '–'} "
            f"({detail.get('user_ratings_total') or hit.get('user_ratings_total') or '?'} Reviews)",
            f"Status: {detail.get('business_status') or hit.get('business_status') or '–'}",
            f"Tel: {detail.get('phone') or detail.get('formatted_phone_number') or '–'}",
            f"Web: {detail.get('website') or '–'}",
            f"Maps: {detail.get('maps_url') or detail.get('url') or '–'}",
        ]
        return {"ok": True, "source": "google_places", "text": "\n".join(lines), "raw": detail}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _register_lookup(text: str) -> dict[str, Any]:
    try:
        from akquise import register as reg

        # Person: zwei Großwörter
        m_pers = re.search(
            r"(?:geschäftsführer|geschaeftsfuehrer|person|über|zu)\s+([A-ZÄÖÜ][\w\-]+(?:\s+[A-ZÄÖÜ][\w\-]+)+)",
            text or "",
        )
        if m_pers and "gmbh" not in m_pers.group(1).lower():
            r = reg.lookup_person(m_pers.group(1).strip())
            if r.get("found") and r.get("holdings"):
                lines = [f"OpenRegister Person: {r.get('person_name') or m_pers.group(1)}"]
                for h in r["holdings"][:12]:
                    lines.append(f"• {h.get('name')} ({h.get('role') or '–'}) {h.get('city') or ''}".strip())
                return {"ok": True, "source": "openregister", "text": "\n".join(lines), "raw": r}
            return {"ok": False, "error": r.get("error") or "person_not_found", "raw": r}

        m_co = re.search(
            r"([A-ZÄÖÜ][\wÄÖÜäöüß &\-]{2,50}(?:GmbH|UG|AG|e\.?\s*K\.?))",
            text or "",
        )
        firma = m_co.group(1).strip() if m_co else ""
        if not firma:
            m2 = re.search(r"(?:firma|betrieb|unternehmen)\s+([A-ZÄÖÜ][\wÄÖÜäöüß &\-]{2,40})", text or "")
            if m2:
                firma = m2.group(1).strip()
        if not firma:
            return {"ok": False, "error": "keine_firma_erkannt"}
        city = ""
        m_city = re.search(r"\b(?:in|aus)\s+([A-ZÄÖÜ][\w\-äöü]{2,30})\b", text or "")
        if m_city:
            city = m_city.group(1)
        r = reg.lookup_company(firma, city)
        if r.get("found"):
            lines = [
                f"OpenRegister: {r.get('company_name')}",
                f"Register: {r.get('register_id') or '–'} {r.get('register_court') or ''}".strip(),
                f"Quelle: {r.get('source')}",
            ]
            if r.get("managers"):
                lines.append("GF: " + ", ".join(r["managers"]))
            if r.get("openregister_url") or r.get("northdata_url"):
                lines.append(r.get("openregister_url") or r.get("northdata_url") or "")
            return {"ok": True, "source": "openregister", "text": "\n".join(lines), "raw": r}
        return {"ok": False, "error": r.get("error") or r.get("hint") or "nicht_gefunden", "raw": r}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def deep_research(query: str) -> dict[str, Any]:
    """Aggregiert Quellen. text = block für Companion."""
    q = (query or "").strip()
    if not q:
        return {"ok": False, "error": "query fehlt", "text": ""}

    blocks: list[str] = []
    sources: list[str] = []
    errors: list[str] = []

    # 1) Web / Wiki
    try:
        import llm_web

        web = llm_web.gather_context(q)
        if web:
            blocks.append("### Web / Wiki\n" + web)
            sources.append("web")
    except Exception as e:
        errors.append(f"web:{e}")

    # 2) URLs scrapen
    urls = URL_RE.findall(q)
    for u in urls[:2]:
        u = u.rstrip(").,;")
        sc = _scrape_url(u)
        if sc.get("ok") and sc.get("text"):
            note = sc.get("note") or ""
            blocks.append(f"### Website ({sc.get('source')})\n{sc['text'][:2500]}" + (f"\n({note})" if note else ""))
            sources.append(sc.get("source") or "crawl")
        else:
            errors.append(f"scrape:{sc.get('error')}")

    # 3) OpenRegister
    if any(
        x in q.lower()
        for x in ("gmbh", "ug", "ag", "firma", "register", "geschäftsführer", "geschaeftsfuehrer", "holding", "unternehmen")
    ) or looks_like_research(q):
        reg = _register_lookup(q)
        if reg.get("ok") and reg.get("text"):
            blocks.append("### Handelsregister / OpenRegister\n" + reg["text"])
            sources.append("openregister")
        elif reg.get("error") and reg.get("error") not in ("keine_firma_erkannt",):
            errors.append(f"register:{reg.get('error')}")

    # 4) Google Places (Betrieb / Ort)
    if any(
        x in q.lower()
        for x in ("restaurant", "imbiss", "café", "cafe", "laden", "betrieb", "in ", "mechernich", "places", "google")
    ) or (looks_like_research(q) and not urls):
        # Query bereinigen
        pq = re.sub(r"(recherch\w*|analysier\w*|bitte|schau dir|check)\s*", "", q, flags=re.I).strip()
        pl = _places_lookup(pq[:120] or q[:120])
        if pl.get("ok") and pl.get("text"):
            blocks.append("### Google Places\n" + pl["text"])
            sources.append("google_places")
            # Website aus Places nachcrawlen
            website = ""
            raw = pl.get("raw") or {}
            if isinstance(raw, dict):
                website = (raw.get("website") or "").strip()
            if website and website not in urls:
                sc2 = _scrape_url(website)
                if sc2.get("ok") and sc2.get("text"):
                    blocks.append(f"### Website aus Places ({sc2.get('source')})\n{sc2['text'][:2000]}")
                    sources.append(sc2.get("source") or "crawl")
        elif pl.get("error"):
            errors.append(f"places:{pl.get('error')}")

    text = "\n\n".join(blocks).strip()
    if not text:
        text = (
            "Keine belastbaren Live-Quellen gefunden. "
            + (f"Hinweise: {'; '.join(errors[:4])}" if errors else "Query enger machen (Firma, Stadt, URL).")
        )
        return {"ok": False, "text": text, "sources": sources, "errors": errors}

    header = "Research-Quellen (belegt): " + ", ".join(sources) if sources else "Research:"
    if errors:
        header += f" | Teilfehler: {', '.join(errors[:3])}"
    return {
        "ok": True,
        "text": f"{header}\n\n{text}"[:5500],
        "sources": sources,
        "errors": errors,
    }

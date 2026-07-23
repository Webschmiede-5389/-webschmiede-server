"""Kostenlose Web-Hilfen für Nils: Wetter + kurze Suche (ohne bezahlte APIs)."""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Any


def needs_live_facts(text: str) -> bool:
    t = (text or "").lower()
    keys = (
        "wetter",
        "temperatur",
        "regen",
        "schnee",
        "aktuell",
        "nachrichten",
        "news",
        "heute",
        "preis von",
        "kurs",
        "wer ist",
        "was ist",
        "was sind",
        "suche",
        "google",
        "wie spät",
        "uhrzeit",
        "börse",
        "aktie",
        "analysier",
        "recherch",
        "firma",
        "geschäftsführer",
        "geschaeftsfuehrer",
        "holding",
        "impressum",
        "bericht",
        "konkurrenz",
        "vergleich",
        "trend",
        "markt",
        "gesetz",
        "dsgvo",
        "wie viel",
        "wo liegt",
        "definition",
        "bedeutet",
        "erkläre",
        "erklaere",
    )
    if any(k in t for k in keys):
        return True
    # Fragezeichen + Substanz = oft Live-Bedarf
    if "?" in t and len(t) > 25:
        return True
    return False


def gather_context(text: str) -> str:
    """Sammelt Live-Fakten: Wetter, Suche, Wikipedia-Kurzinfo."""
    parts: list[str] = []
    t = (text or "").strip()
    if not t:
        return ""
    low = t.lower()
    if any(k in low for k in ("wetter", "temperatur", "regen", "schnee", "grad")):
        w = weather_for_text(t)
        if w.get("ok"):
            parts.append(w["text"])
        elif w.get("error"):
            parts.append(f"Wetter: {w['error']}")
    want_search = needs_live_facts(t) or (
        not parts and ("?" in t or len(t) > 40)
    )
    if want_search:
        if not (parts and "wetter" in low and len(low) < 40):
            s = web_search(t, limit=5)
            if s.get("ok") and s.get("text"):
                parts.append(s["text"])
            wiki = wikipedia_summary(t)
            if wiki.get("ok") and wiki.get("text"):
                parts.append(wiki["text"])
    return "\n\n".join(parts)[:5500]


def wikipedia_summary(query: str) -> dict[str, Any]:
    """Deutsche Wikipedia-Kurzfassung (gratis)."""
    q = (query or "").strip()
    # Titel grob aus Frage ziehen
    m = re.search(
        r"(?:wer ist|was ist|was sind|erkläre|erklaere|definition(?:\s+von)?)\s+(.+?)(?:\?|$)",
        q,
        re.I,
    )
    title = (m.group(1) if m else q).strip(" ?.!,")
    title = re.sub(r"^(der|die|das|ein|eine)\s+", "", title, flags=re.I)
    if len(title) < 2 or len(title) > 80:
        return {"ok": False, "error": "no_title"}
    try:
        url = (
            "https://de.wikipedia.org/api/rest_v1/page/summary/"
            + urllib.parse.quote(title.replace(" ", "_"))
        )
        data = _get_json(url, timeout=10)
        extract = (data.get("extract") or "").strip()
        if not extract:
            return {"ok": False, "error": "empty"}
        page = data.get("content_urls", {}).get("desktop", {}).get("page") or ""
        line = f"Wikipedia: {extract[:700]}"
        if page:
            line += f" ({page})"
        return {"ok": True, "text": line}
    except Exception:
        return {"ok": False, "error": "wiki_fail"}


def weather_for_text(text: str) -> dict[str, Any]:
    """Open-Meteo (gratis). Ort aus Text oder Default Mechernich."""
    place = _extract_place(text) or "Mechernich"
    geo = _geocode(place)
    if not geo:
        return {"ok": False, "error": f"Ort „{place}“ nicht gefunden"}
    lat, lon, label = geo
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast?"
            + urllib.parse.urlencode(
                {
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code",
                    "timezone": "Europe/Berlin",
                    "forecast_days": 2,
                }
            )
        )
        data = _get_json(url, timeout=12)
        cur = data.get("current") or {}
        daily = data.get("daily") or {}
        code = cur.get("weather_code")
        line = (
            f"Wetter jetzt in {label}: {_wmo(code)}, "
            f"{cur.get('temperature_2m')}°C, Luftfeuchte {cur.get('relative_humidity_2m')}%, "
            f"Wind {cur.get('wind_speed_10m')} km/h."
        )
        if daily.get("time"):
            line += (
                f" Heute max {daily['temperature_2m_max'][0]}°C / min {daily['temperature_2m_min'][0]}°C, "
                f"Niederschlag {daily.get('precipitation_sum', [0])[0]} mm."
            )
            if len(daily["time"]) > 1:
                line += (
                    f" Morgen max {daily['temperature_2m_max'][1]}°C / "
                    f"min {daily['temperature_2m_min'][1]}°C."
                )
        return {"ok": True, "text": line, "place": label}
    except Exception as e:
        return {"ok": False, "error": f"Wetter-API: {type(e).__name__}"}


def web_search(query: str, *, limit: int = 4) -> dict[str, Any]:
    """DuckDuckGo Instant Answer + HTML-Fallback (ohne Key)."""
    q = (query or "").strip()
    if not q:
        return {"ok": False, "error": "leere Suche"}
    lines: list[str] = []
    try:
        ia = _get_json(
            "https://api.duckduckgo.com/?"
            + urllib.parse.urlencode({"q": q, "format": "json", "no_html": 1, "skip_disambig": 1}),
            timeout=10,
        )
        abs_ = (ia.get("AbstractText") or "").strip()
        if abs_:
            src = ia.get("AbstractURL") or ia.get("AbstractSource") or "DuckDuckGo"
            lines.append(f"Kurz: {abs_} ({src})")
        for t in (ia.get("RelatedTopics") or [])[:3]:
            if isinstance(t, dict) and t.get("Text"):
                lines.append(f"- {t['Text'][:220]}")
    except Exception:
        pass
    if len(lines) < 2:
        try:
            html = _get_text(
                "https://html.duckduckgo.com/html/?"
                + urllib.parse.urlencode({"q": q}),
                timeout=12,
            )
            # grobe Snippets
            titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, flags=re.I | re.S)
            snips = re.findall(r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div)', html, flags=re.I | re.S)
            for i, title in enumerate(titles[:limit]):
                title_c = re.sub(r"<[^>]+>", "", title).strip()
                snip = ""
                if i < len(snips):
                    snip = re.sub(r"<[^>]+>", "", snips[i]).strip()
                if title_c:
                    lines.append(f"- {title_c}" + (f": {snip[:180]}" if snip else ""))
        except Exception:
            pass
    if not lines:
        return {"ok": False, "error": "keine Suchtreffer"}
    return {"ok": True, "text": "Web-Recherche:\n" + "\n".join(lines[:limit])}


def _extract_place(text: str) -> str | None:
    t = text or ""
    m = re.search(
        r"(?:wetter|temperatur|regen)\s+(?:in|für|fuer)\s+([A-Za-zÄÖÜäöüß\- ]{2,40})",
        t,
        re.I,
    )
    if m:
        return m.group(1).strip(" ?.!,")
    m = re.search(r"\bin\s+([A-ZÄÖÜ][A-Za-zÄÖÜäöüß\- ]{1,36})", t)
    if m:
        cand = m.group(1).strip(" ?.!,")
        if cand.lower() not in ("der", "die", "dem", "den"):
            return cand
    return None


def _geocode(place: str) -> tuple[float, float, str] | None:
    try:
        url = "https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(
            {"name": place, "count": 1, "language": "de", "format": "json"}
        )
        data = _get_json(url, timeout=10)
        results = data.get("results") or []
        if not results:
            return None
        r0 = results[0]
        label = ", ".join(
            x for x in (r0.get("name"), r0.get("admin1"), r0.get("country_code")) if x
        )
        return float(r0["latitude"]), float(r0["longitude"]), label
    except Exception:
        return None


def _wmo(code: Any) -> str:
    try:
        c = int(code)
    except Exception:
        return "unbekannt"
    table = {
        0: "klar",
        1: "meist klar",
        2: "teilweise bewölkt",
        3: "bedeckt",
        45: "Nebel",
        48: "Nebel",
        51: "leichter Nieselregen",
        61: "leichter Regen",
        63: "Regen",
        65: "starker Regen",
        71: "leichter Schnee",
        73: "Schnee",
        75: "starker Schnee",
        80: "Regenschauer",
        95: "Gewitter",
    }
    return table.get(c, f"Code {c}")


def _get_json(url: str, *, timeout: float) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "WebschmiedeNils/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def _get_text(url: str, *, timeout: float) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "WebschmiedeNils/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")

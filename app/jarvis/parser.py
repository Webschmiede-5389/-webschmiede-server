"""Nachrichten parsen: Gericht finden, Preis, Text, Verfügbarkeit."""
import re
import unicodedata

from .permissions import normalize_phone


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.lower().strip())


def parse_price(text: str) -> float | None:
    t = text.replace(",", ".")
    m = re.search(r"(?:preis|kostet|jetzt|nur|auf)?\s*(\d+(?:\.\d{1,2})?)\s*(?:€|eur|euro)?", t, re.I)
    if m:
        return round(float(m.group(1)), 2)
    m = re.search(r"(\d+[,\.]\d{2})\s*€?", text)
    if m:
        return round(float(m.group(1).replace(",", ".")), 2)
    return None


def parse_description(text: str) -> str | None:
    for pat in (
        r"(?:beschreibung|text|desc)\s*[:\-]\s*(.+)",
        r"neuer?\s+text\s*[:\-]\s*(.+)",
    ):
        m = re.search(pat, text, re.I | re.S)
        if m:
            return m.group(1).strip()[:500]
    return None


def parse_availability(text: str) -> bool | None:
    low = _norm(text)
    if any(w in low for w in ("ausverkauft", "nicht verfuegbar", "nicht verfügbar", "deaktivieren", "aus")):
        return False
    if any(w in low for w in ("wieder verfuegbar", "wieder verfügbar", "aktivieren", "verfuegbar", "verfügbar")):
        return True
    return None


def find_item(text: str, catalog: list[dict]) -> dict | None:
    if not text or not catalog:
        return None
    low = _norm(text)

    # Explizite ID: "d4" oder "item d4"
    m = re.search(r"\b([a-z]{1,2}\d{1,3})\b", low)
    if m:
        iid = m.group(1)
        for item in catalog:
            if item["id"].lower() == iid:
                return item

    best, best_score = None, 0
    for item in catalog:
        name = _norm(item.get("name", ""))
        if not name:
            continue
        if name in low or low in name:
            score = len(name)
            if score > best_score:
                best, best_score = item, score
        # Wort-Treffer
        words = [w for w in re.split(r"[^\w]+", name) if len(w) > 3]
        hits = sum(1 for w in words if w in low)
        if hits and hits >= max(1, len(words) // 2):
            score = hits * 10
            if score > best_score:
                best, best_score = item, score
    return best


def parse_admin_command(text: str) -> dict | None:
    """Agency-Befehl: 'Kunde SHY001 freischalten +49176...'"""
    m = re.search(
        r"kunde\s+([A-Z0-9]+)\s+freischalten\s+([+\d][\d\s\-]+)",
        text, re.I,
    )
    if m:
        return {"action": "register_phone", "client_id": m.group(1).upper(), "phone": m.group(2).strip()}
    return None

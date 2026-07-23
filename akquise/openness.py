"""Digital-Offenheit & Generations-/Nachfolge-Signale (Proxy aus Web-Daten)."""
from __future__ import annotations

import re
from typing import Any

TRADITION_PATTERNS = [
    r"seit\s+(19|20)\d{2}",
    r"tradition",
    r"familienbetrieb",
    r"in\s+(dritter|zweiter|vierter)\s+generation",
    r"wie\s+(schon\s+)?immer",
    r"bewährt",
    r"original\s+rezept",
]

SUCCESSION_PATTERNS = [
    r"nachfolge",
    r"neu\s+eröffnet",
    r"neu\s+eroffnet",
    r"under\s+new",
    r"frisch\s+übernommen",
    r"frisch\s+uebernommen",
    r"junge\s+generation",
    r"2\.\s+generation",
    r"neues\s+team",
    r"relauch",
    r"relaunch",
]

RESISTANCE_PATTERNS = [
    r"handwerk",
    r"ohne\s+schnickschnack",
    r"authentisch",
    r"urig",
    r"gemütlich(?:keit)?",
    r"wie\s+früher",
]

YOUNG_PATTERNS = [
    r"instagram",
    r"tiktok",
    r"story",
    r"vegan",
    r"bowl",
    r"craft\s+beer",
    r"events?",
    r"live\s+musik",
]


def scan_culture_signals(html: str) -> dict:
    text = re.sub(r"<[^>]+>", " ", (html or "")[:80000]).lower()
    text = re.sub(r"\s+", " ", text)

    def hits(patterns: list[str]) -> list[str]:
        return [p for p in patterns if re.search(p, text)]

    tradition = hits(TRADITION_PATTERNS)
    succession = hits(SUCCESSION_PATTERNS)
    resistance = hits(RESISTANCE_PATTERNS)
    young = hits(YOUNG_PATTERNS)

    return {
        "tradition_signals": tradition[:3],
        "succession_signals": succession[:3],
        "resistance_signals": resistance[:3],
        "young_signals": young[:3],
    }


def assess_openness(lead: dict, sig: dict, revenue: dict, problems: list[dict]) -> dict[str, Any]:
    score = 50
    reasons: list[str] = []

    if sig.get("succession_signals"):
        score += 22
        reasons.append("Nachfolge/Neustart-Signal, oft offener für Digital")
    if sig.get("young_signals") or "instagram" in (sig.get("social") or []):
        score += 12
        reasons.append("Aktiv auf Social, jüngere Zielgruppe erreichbar")
    if sig.get("order_signals") or sig.get("delivery_platforms"):
        score += 15
        reasons.append("Nutzt schon digitale Kanäle")
    if sig.get("job_signals"):
        score += 8
        reasons.append("Personalmangel, Schmerz = Offenheit für Entlastung")

    if sig.get("tradition_signals"):
        score -= 18
        reasons.append("Traditions-Sprache, „läuft schon immer so“-Risiko")
    if sig.get("resistance_signals"):
        score -= 10
        reasons.append("Uriger/anti-modern Ton")
    if sig.get("only_social_site") and not sig.get("succession_signals"):
        score -= 15
        reasons.append("Nur Facebook, oft ältere Inhaber, hartes Gespräch")
    amenity = (lead.get("amenity") or "").lower()
    name = (lead.get("name") or "").lower()
    if amenity in ("bar", "pub") or "kneipe" in name or "pief" in name:
        score -= 12
        reasons.append("Pub/Kneipe, klassisch „Telefon reicht“-Mentalität")

    if not revenue.get("can_afford_setup"):
        score -= 8
        reasons.append("Geschätzter Umsatz niedrig, eher Starter/Quick-Wins")

    high_problems = sum(1 for p in problems if p.get("severity") == "high")
    if high_problems >= 3:
        score += 10
        reasons.append("Viele versteckte Probleme, Beratungshebel wenn Gespräch klappt")

    score = max(0, min(100, score))

    if score >= 68:
        tier, label, approach = "offen", "Eher offen", "Direkt ansprechen, Problem → Lösung zeigen"
    elif score >= 48:
        tier, label, approach = "neutral", "Neutral", "Erst Schmerz sichtbar machen (Zahlen, Nachbar-Vergleich)"
    elif score >= 32:
        tier, label, approach = "tradition", "Traditionell", "Nicht verkaufen, kostenloser Check, Nachfolger ansprechen"
    else:
        tier, label, approach = "resistent", "Eher resistent", "Nicht anrufen, nur wenn Nachfolge/Inhaberwechsel"

    successor_hint = ""
    if sig.get("succession_signals"):
        successor_hint = "Nachfolge/Neustart erkannt, jüngere Generation ansprechen"
    elif sig.get("tradition_signals") and sig.get("only_social_site"):
        successor_hint = "Tipp: Nach Inhaberwechsel erneut scannen oder Enkel/Nachfolger suchen"

    return {
        "score": score,
        "tier": tier,
        "label": label,
        "approach": approach,
        "reasons": reasons[:4],
        "reason_summary": " · ".join(reasons[:2]) if reasons else "–",
        "successor_hint": successor_hint,
        "call_despite_budget": score >= 55 and revenue.get("can_afford_monthly"),
    }

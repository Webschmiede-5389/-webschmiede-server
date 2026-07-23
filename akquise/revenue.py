"""Umsatz-Schätzung aus öffentlichen Signalen (Heuristik, keine Buchhaltung)."""
from __future__ import annotations

# Basis-Monatsumsatz € nach Betriebstyp (Kleinbetrieb NRW, Schätzung)
AMENITY_BASE: dict[str, int] = {
    "restaurant": 22000,
    "fast_food": 16000,
    "cafe": 11000,
    "bar": 14000,
    "pub": 13000,
    "biergarten": 18000,
    "ice_cream": 9000,
    "food_court": 35000,
    "plumber": 25000,
    "electrician": 28000,
    "carpenter": 22000,
    "painter": 18000,
    "roofer": 30000,
    "default": 15000,
}


def estimate_revenue(lead: dict, sig: dict) -> dict:
    amenity = (lead.get("amenity") or "default").lower()
    base = AMENITY_BASE.get(amenity, AMENITY_BASE["default"])
    mult = 1.0
    factors: list[str] = []

    gp = lead.get("google_places") or {}
    reviews = int(gp.get("user_ratings_total") or 0)
    rating = gp.get("rating")

    if reviews > 150:
        mult *= 1.45
        factors.append(f"viele Bewertungen ({reviews})")
    elif reviews > 60:
        mult *= 1.25
        factors.append(f"solide Bewertungen ({reviews})")
    elif reviews > 15:
        mult *= 1.05
    elif reviews > 0:
        mult *= 0.85
        factors.append("wenig Google-Sichtbarkeit")
    else:
        mult *= 0.75
        factors.append("kaum/keine Google-Daten")

    if rating and float(rating) >= 4.3:
        mult *= 1.08
    elif rating and float(rating) < 3.8:
        mult *= 0.88
        factors.append(f"schwaches Rating ({rating}★)")

    if sig.get("delivery_platforms"):
        mult *= 1.35
        factors.append("Liefergeschäft aktiv")

    if sig.get("only_social_site"):
        mult *= 0.72
        factors.append("nur Social, unter Durchschnitt digital")
    elif not sig.get("has_website"):
        mult *= 0.78
        factors.append("keine Website")

    if sig.get("order_signals") and not sig.get("delivery_platforms"):
        mult *= 1.12
        factors.append("eigenes Bestellen")

    if sig.get("job_signals"):
        mult *= 0.92
        factors.append("Personalmangel-Signal")

    name = (lead.get("name") or "").lower()
    if any(x in name for x in ("kneipe", "pub", "pief", "brauhaus")):
        base = AMENITY_BASE.get("pub", 13000)
        if not sig.get("order_signals"):
            mult *= 0.88
            factors.append("Pub/Kneipe ohne Bestellkanal")

    if sig.get("tradition_signals"):
        mult *= 0.9
        factors.append("Traditionsbetrieb, eher stabil/stagnierend")

    monthly = int(base * mult)
    lo = int(monthly * 0.75)
    hi = int(monthly * 1.25)

    # Digitalisierungs-Potenzial (was zusätzlich möglich wäre)
    uplift = 0
    if sig.get("delivery_platforms"):
        uplift += int(monthly * 0.08)
    elif not sig.get("order_signals"):
        uplift += int(monthly * 0.12)
    if sig.get("only_social_site"):
        uplift += int(monthly * 0.06)

    return {
        "monthly_est": monthly,
        "range": f"{lo:,}–{hi:,} €/Monat".replace(",", "."),
        "label": f"ca. {lo:,}–{hi:,} €/Monat".replace(",", "."),
        "confidence": "niedrig" if not reviews and not sig.get("checked") else ("mittel" if reviews < 30 else "hoch"),
        "factors": factors[:4],
        "digital_uplift_est": f"+{uplift:,} €/Mo möglich".replace(",", ".") if uplift else "–",
        "can_afford_setup": monthly >= 18000 and not sig.get("only_social_site"),
        "can_afford_monthly": monthly >= 12000 or bool(sig.get("delivery_platforms")),
    }

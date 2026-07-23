"""Zahlungsbereitschaft schätzen · Zeit nur bei passenden Leads."""
from __future__ import annotations

from typing import Any

from buy_signals import apply_buy_signals_to_budget, detect_buy_signals


def assess_budget(lead: dict, sig: dict, providers: list[dict], vertical: dict) -> dict[str, Any]:
    score = 50
    reasons: list[str] = []
    vid = vertical.get("vertical") or vertical.get("id", "")

    paid = [p for p in providers if (p.get("monthly_min") or 0) > 0]
    delivery = [p for p in providers if p.get("category") == "delivery"]

    if delivery:
        score += 28
        reasons.append(f"Zahlt bereits {delivery[0]['name']}, Budget für Digital da, ROI-Rechnung zeigen")
    elif paid:
        score += 18
        reasons.append(f"Nutzt kostenpflichtige Tools ({paid[0]['name']}), investiert in Digital")

    if sig.get("runs_facebook_ads"):
        score += 22
        reasons.append("Läuft Meta-Werbung, Marketing-Budget vorhanden")

    gp = lead.get("google_places") or {}
    reviews = int(gp.get("user_ratings_total") or 0)
    rating = gp.get("rating")
    if reviews > 80:
        score += 15
        reasons.append(f"Etabliert ({reviews} Google-Bewertungen), Umsatz wahrscheinlich")
    elif reviews > 25:
        score += 8
        reasons.append("Solide Google-Präsenz")

    if rating and float(rating) >= 4.2 and reviews > 15:
        score += 5

    lf = (sig.get("legal_form") or "").lower()
    if "gmbh" in lf or "ug" in lf:
        score += 12
        reasons.append("GmbH/UG, höhere Zahlungsfähigkeit wahrscheinlich")
    elif "e.k" in lf or "ek" in lf.replace(".", ""):
        score += 4

    if sig.get("order_signals") and sig.get("has_website"):
        score += 10
        reasons.append("Bereits Online-Bestellen/Anfrage, Upgrade statt Cold Start")

    if sig.get("impressum_checked") and (sig.get("contact_emails") or sig.get("contact_person")):
        score += 5

    if sig.get("only_social_site"):
        score -= 30
        reasons.append("Nur Social, oft kein Budget für 1.500 € Setup; erst Einstiegspaket")
    elif not sig.get("has_website"):
        score -= 22
        reasons.append("Keine Website, eher langsam starten (kostenlose Quick-Wins)")

    if not sig.get("has_website") and not delivery and not paid:
        score -= 10
        reasons.append("Kein Digital-Spend erkennbar")

    if sig.get("job_signals") and not delivery and not paid:
        score -= 8
        reasons.append("Sucht Personal ohne Digital-Tools, evtl. knapp bei Kasse")

    if sig.get("cms") == ["jimdo"] and not sig.get("order_signals") and not delivery:
        score -= 5
        reasons.append("Minimal-Jimdo, kleines Budget-Signal")

    if sig.get("status_code", 0) >= 400 or sig.get("error"):
        score -= 5

    score = max(0, min(100, score))

    if score >= 72:
        tier, label, priority = "A", "Zahlungsbereit", "call"
        action = "Anrufen, Standard-Angebot + ROI gegen erkannte Kosten"
    elif score >= 55:
        tier, label, priority = "B", "Gespräch wert", "call"
        action = "Anrufen, gestaffeltes Angebot (Setup in Raten oder Starter-Paket)"
    elif score >= 38:
        tier, label, priority = "C", "Erst lokal / günstig", "nurture"
        action = "Nicht sofort verkaufen, kostenlose Quick-Wins, später Upgrade"
    else:
        tier, label, priority = "D", "Später", "skip"
        action = "Nicht anrufen, in Nurture-Liste oder ignorieren"

    offers = vertical.get("offers") or {}
    offer_key = _pick_offer(tier, sig, providers, vid)
    offer = offers.get(offer_key, {})

    budget = {
        "score": score,
        "tier": tier,
        "label": label,
        "contact_priority": priority,
        "action": action,
        "reasons": reasons[:4],
        "reason_summary": " · ".join(reasons[:2]) if reasons else "Neutral",
        "offer_key": offer_key,
        "offer_name": offer.get("name", ""),
        "offer_setup": offer.get("setup", ""),
        "offer_monthly": offer.get("monthly", ""),
        "offer_includes": offer.get("includes", []),
    }

    signals = detect_buy_signals(lead, sig, providers)
    budget = apply_buy_signals_to_budget(budget, signals)

    offer_key = _pick_offer(budget["tier"], sig, providers, vid)
    offer = offers.get(offer_key, {})
    budget["offer_key"] = offer_key
    budget["offer_name"] = offer.get("name", "")
    budget["offer_setup"] = offer.get("setup", "")
    budget["offer_monthly"] = offer.get("monthly", "")
    budget["offer_includes"] = offer.get("includes", [])
    return budget


def _pick_offer(tier: str, sig: dict, providers: list[dict], vertical_id: str) -> str:
    has_delivery = any(p.get("category") == "delivery" for p in providers)
    if tier == "A":
        if has_delivery or sig.get("order_signals"):
            return "premium" if vertical_id == "gastro" else "standard"
        return "standard"
    if tier == "B":
        return "standard" if sig.get("has_website") else "starter"
    if tier == "C":
        return "local"
    return "local"

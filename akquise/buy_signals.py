# -*- coding: utf-8 -*-
"""Kaufbereitschaft: die 3 schärfsten Signale für A/B-Anrufe.

1. Zahlt schon Digital (Lieferando/Tools), aber Lücke (kein eigenes Bestellen/Anfrage)
2. Meta-Ads laufen, Funnel fehlt
3. Personal gesucht + Digital schwach

Add-on-Pitch: bestehendes Tool bleibt, Webschmiede dockt an.
"""
from __future__ import annotations

from typing import Any


def detect_buy_signals(lead: dict, sig: dict, providers: list[dict]) -> list[dict[str, Any]]:
    gp = lead.get("google_places") or {}
    reviews = int(gp.get("user_ratings_total") or 0)
    rating = gp.get("rating")
    try:
        rating_f = float(rating) if rating is not None else None
    except (TypeError, ValueError):
        rating_f = None

    delivery = [p for p in providers if p.get("category") == "delivery"]
    handwerk_sw = [p for p in providers if p.get("category") == "handwerk_software"]
    paid = [p for p in providers if (p.get("monthly_min") or 0) > 0]
    has_own_order = bool(sig.get("order_signals"))
    weak_web = (
        not sig.get("has_website")
        or sig.get("only_social_site")
        or not sig.get("https")
        or (sig.get("status_code") or 0) >= 400
    )
    no_lead_capture = sig.get("checked") and not has_own_order and sig.get("has_website") and not sig.get("only_social_site")

    out: list[dict[str, Any]] = []

    # 1) Zahlt Plattform/Tool, eigene Bestellung/Anfrage fehlt → Add-on
    if delivery and not has_own_order:
        name = delivery[0].get("name", "Lieferdienst")
        out.append(
            {
                "id": "paid_delivery_gap",
                "label": f"Zahlt {name}, kein eigenes Bestellen",
                "heat": "hot",
                "score_boost": 26,
                "addon": f"{name} bleibt für Neukunden, eigenes Portal für Stammkunden + SMS-Link",
                "why_buy": "Zahlt schon Digital-Provision, Add-on spart Marge sofort",
            }
        )
    elif handwerk_sw and no_lead_capture:
        name = handwerk_sw[0].get("name", "Handwerk-Software")
        out.append(
            {
                "id": "paid_handwerk_gap",
                "label": f"Nutzt {name}, keine Online-Anfrage",
                "heat": "hot",
                "score_boost": 22,
                "addon": f"Website-Anfragen landen in {name}, Tool bleibt",
                "why_buy": "Zahlt schon Büro-Software, braucht nur mehr eingehende Aufträge",
            }
        )
    elif paid and (weak_web or no_lead_capture):
        name = paid[0].get("name", "Digital-Tool")
        out.append(
            {
                "id": "paid_stack_gap",
                "label": f"Zahlt {name}, Auftritt/Funnel lückenhaft",
                "heat": "warm",
                "score_boost": 16,
                "addon": "Bestehenden Stack behalten, fehlenden Baustein ergänzen",
                "why_buy": "Budget ist da, Lücke ist klar",
            }
        )

    # 2) Meta-Ads ohne Conversion
    if sig.get("runs_facebook_ads") and (weak_web or not has_own_order):
        out.append(
            {
                "id": "ads_no_funnel",
                "label": "Meta-Ads an, Funnel fehlt",
                "heat": "hot",
                "score_boost": 24,
                "addon": "Landing + Bestellen/Anfrage + CRM, Ads-Geld kommt an",
                "why_buy": "Verbrennt schon Werbebudget ohne Zielseite",
            }
        )

    # 3) Jobs + Digital schwach (oder Trust-Loch bei laufendem Betrieb)
    if sig.get("job_signals") and (weak_web or not has_own_order):
        out.append(
            {
                "id": "jobs_digital_gap",
                "label": "Personal gesucht + Digital schwach",
                "heat": "hot",
                "score_boost": 20,
                "addon": "Anfragen/Bestellungen automatisieren, Chef weg vom Telefon",
                "why_buy": "Will entlasten, Digital ist der Hebel ohne neue Stelle",
            }
        )
    elif rating_f is not None and rating_f < 4.0 and reviews >= 8 and (weak_web or not has_own_order):
        out.append(
            {
                "id": "trust_gap",
                "label": f"Google schwach ({rating_f}★) + Auftritt lückenhaft",
                "heat": "warm",
                "score_boost": 14,
                "addon": "Review-Funnel + sichtbarer Auftritt, Konkurrenz einholen",
                "why_buy": "Verliert Vertrauen online, spürbarer Schmerz",
            }
        )

    status = (gp.get("business_status") or "").upper()
    if status == "CLOSED_TEMPORARILY":
        out.append(
            {
                "id": "temp_closed",
                "label": "Google: vorübergehend geschlossen",
                "heat": "warm",
                "score_boost": 12,
                "addon": "Wiedereröffnung mit starkem Online-Auftritt begleiten",
                "why_buy": "Umbruch, oft neuer digitaler Start",
            }
        )
    open_now = gp.get("open_now")
    if open_now is False and status == "OPERATIONAL" and reviews >= 20:
        if weak_web or not has_own_order:
            out.append(
                {
                    "id": "hours_friction",
                    "label": "Gerade zu / Stoßzeiten-Engpass wahrscheinlich",
                    "heat": "warm",
                    "score_boost": 8,
                    "addon": "Online-Anfrage/Bestellen außerhalb der Stoßzeiten",
                    "why_buy": "Ohne Digitalkanal sterben Anfragen wenn zu ist",
                }
            )

    # Dedup by id
    seen: set[str] = set()
    uniq: list[dict[str, Any]] = []
    for s in out:
        if s["id"] in seen:
            continue
        seen.add(s["id"])
        uniq.append(s)
    return uniq


def apply_buy_signals_to_budget(budget: dict, signals: list[dict]) -> dict:
    """Score anheben, A/B erzwingen wenn heiß genug."""
    if not signals:
        budget["buy_signals"] = []
        budget["buy_ready"] = False
        budget["buy_summary"] = ""
        budget["addon_pitch"] = ""
        return budget

    boost = sum(int(s.get("score_boost") or 0) for s in signals)
    # Cap: nicht endlos stapeln
    boost = min(boost, 40)
    score = min(100, int(budget.get("score") or 0) + boost)
    budget["score"] = score

    reasons = list(budget.get("reasons") or [])
    for s in signals[:3]:
        reasons.insert(0, s.get("why_buy") or s.get("label") or "")
    budget["reasons"] = reasons[:5]
    budget["reason_summary"] = " · ".join(reasons[:2])

    hot_n = sum(1 for s in signals if s.get("heat") == "hot")
    # Schwellen: mit Kauf-Signalen leichter A/B
    if score >= 68 or hot_n >= 2:
        tier, label, priority = "A", "Kaufbereit (Signal)", "call"
        action = "Anrufen: Add-on-Pitch, bestehendes Tool bleibt"
    elif score >= 52 or hot_n >= 1:
        tier, label, priority = "B", "Gespräch heiß", "call"
        action = "Anrufen: Lücke + Add-on zeigen, ROI gegen laufende Kosten"
    elif score >= 38:
        tier, label, priority = "C", "Erst lokal / günstig", "nurture"
        action = budget.get("action") or "Quick-Wins, später Upgrade"
    else:
        tier, label, priority = "D", "Später", "skip"
        action = budget.get("action") or "Nicht anrufen"

    budget["tier"] = tier
    budget["label"] = label
    budget["contact_priority"] = priority
    budget["action"] = action
    budget["buy_signals"] = signals
    budget["buy_ready"] = tier in ("A", "B") and len(signals) >= 1
    budget["buy_summary"] = " · ".join(s["label"] for s in signals[:3])
    budget["addon_pitch"] = signals[0].get("addon") or ""
    return budget

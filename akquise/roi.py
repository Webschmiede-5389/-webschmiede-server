# -*- coding: utf-8 -*-
"""ROI-Schätzung: laufende Kosten vs. Add-on-Nutzen (Heuristik)."""
from __future__ import annotations

from typing import Any

from addons import resolve_addon


def estimate_roi(
    lead: dict,
    sig: dict,
    providers: list[dict],
    revenue: dict,
    buy_signals: list[dict] | None = None,
) -> dict[str, Any]:
    buy_signals = buy_signals or []
    addon = resolve_addon(providers, buy_signals)

    spend_min = sum(int(p.get("monthly_min") or 0) for p in providers)
    # Delivery: typische Provision grob als €/Mo aus Reviews ableiten
    delivery = [p for p in providers if p.get("category") == "delivery"]
    gp = lead.get("google_places") or {}
    reviews = int(gp.get("user_ratings_total") or 0)
    delivery_bleed = 0
    if delivery:
        delivery_bleed = min(600, max(80, int(reviews * 1.8)))

    current_monthly_drag = spend_min + delivery_bleed
    uplift = int(addon.get("roi_hint_monthly") or 150)

    # Wenn digital_uplift_est als Text da ist, Score aus Revenue nutzen
    rev_month = int(revenue.get("monthly_est") or 0)
    if rev_month and delivery:
        # 8–12 % des geschätzten Liefer-Anteils als Sparpotenzial
        uplift = max(uplift, int(rev_month * 0.04))

    setup_ref = 1980  # typisches Standard-Setup Untergrenze
    payback = round(setup_ref / uplift, 1) if uplift else None

    return {
        "current_monthly_drag_eur": current_monthly_drag,
        "addon_uplift_eur": uplift,
        "setup_ref_eur": setup_ref,
        "payback_months": payback,
        "label": (
            f"ca. {uplift} EUR/Mo Mehrwert (Schätzung), "
            f"Setup ab {setup_ref} EUR = ca. {payback} Mo Amortisation"
            if payback
            else f"ca. {uplift} EUR/Mo Mehrwert (Schätzung)"
        ),
        "addon_keep": addon.get("keep", ""),
        "addon_do": addon.get("addon", ""),
        "addon_value": addon.get("value", ""),
        "provider_name": addon.get("provider_name", ""),
    }

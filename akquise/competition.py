"""Lokal-Ranking: digitaler Index vs. Nachbarn in gleicher Stadt."""
from __future__ import annotations

import re


def _city(lead: dict) -> str:
    addr = lead.get("address") or ""
    parts = [p.strip() for p in addr.split(",")]
    for p in reversed(parts):
        m = re.search(r"\d{5}\s+(.+)", p)
        if m:
            return m.group(1).strip().lower()
        if p and not re.match(r"^\d", p):
            return p.lower()
    return "unknown"


def digital_index(lead: dict) -> float:
    sig = lead.get("signals") or {}
    gp = lead.get("google_places") or {}
    idx = float(lead.get("score", 0))
    reviews = int(gp.get("user_ratings_total") or 0)
    rating = gp.get("rating") or 0
    idx += min(reviews, 200) * 0.15
    if rating:
        idx += float(rating) * 4
    if sig.get("order_signals"):
        idx += 15
    if sig.get("delivery_platforms"):
        idx += 10
    if sig.get("runs_facebook_ads"):
        idx += 12
    if sig.get("only_social_site"):
        idx -= 20
    if not sig.get("has_website"):
        idx -= 15
    if sig.get("https"):
        idx += 5
    if sig.get("mobile_viewport"):
        idx += 5
    return round(idx, 1)


def rank_leads_locally(leads: list[dict]) -> int:
    by_city: dict[str, list[tuple[float, dict]]] = {}
    for lead in leads:
        city = _city(lead)
        idx = digital_index(lead)
        lead["digital_index"] = idx
        by_city.setdefault(city, []).append((idx, lead))

    ranked = 0
    for city, group in by_city.items():
        if city == "unknown" or len(group) < 2:
            for _, lead in group:
                lead["local_rank"] = {"rank": 1, "total": 1, "city": city, "ahead": 0, "label": "–"}
            continue
        group.sort(key=lambda x: -x[0])
        total = len(group)
        for i, (idx, lead) in enumerate(group, 1):
            ahead = i - 1
            behind = total - i
            label = f"#{i} von {total} in {city.title()}"
            if ahead == 0:
                pitch = f"Lokal digital führend in {city.title()}"
            elif ahead <= 2:
                pitch = f"{ahead} Konkurrent(en) digital stärker, aufholen möglich"
            else:
                pitch = f"{ahead} Betriebe in {city.title()} digital vor dir, Lokal-Matador-Potenzial"
            lead["local_rank"] = {
                "rank": i,
                "total": total,
                "city": city,
                "ahead": ahead,
                "behind": behind,
                "label": label,
                "pitch": pitch,
            }
            ranked += 1
    return ranked

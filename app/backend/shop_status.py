# -*- coding: utf-8 -*-
"""Serverseitige Source of Truth für Öffnungs- und Bestellstatus (Europe/Berlin).

Ein Tenant (kunden/*.json location.*) + DB-Settings (online/offline, waits)
→ ein Status-Objekt für Startseite, Bestellportal, Admin und Order-Guard.
"""
from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

DAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
# datetime.weekday(): Mon=0 … Sun=6
WEEKDAY_TO_KEY = {i: DAY_KEYS[i] for i in range(7)}

DEFAULT_TZ = "Europe/Berlin"

# Legacy-Fallback, wenn Tenant-JSON noch keine location.hours hat (SHY001 Ist-Stand).
DEFAULT_REGULAR_HOURS: dict[str, list[list[str]]] = {
    "mon": [["11:00", "21:00"]],
    "tue": [["11:00", "21:00"]],
    "wed": [],
    "thu": [["11:00", "21:00"]],
    "fri": [["11:00", "21:00"]],
    "sat": [["11:00", "21:00"]],
    "sun": [["11:00", "21:00"]],
}


def _parse_hhmm(value: str) -> time:
    parts = (value or "").strip().split(":")
    if len(parts) < 2:
        raise ValueError(f"Ungültige Uhrzeit: {value!r}")
    return time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)


def _in_interval(now_t: time, start_s: str, end_s: str) -> bool:
    start = _parse_hhmm(start_s)
    end = _parse_hhmm(end_s)
    # Ende exklusiv (11–21 → bis 20:59:59), wie bisherige Client-Logik mins < 21*60
    return start <= now_t < end


def load_location_config(kunde: dict | None) -> dict[str, Any]:
    """Normalisierte Standortkonfiguration aus Tenant-JSON."""
    loc = dict((kunde or {}).get("location") or {})
    hours = dict(loc.get("hours") or {})
    regular = hours.get("regular") or DEFAULT_REGULAR_HOURS
    fulfillment = dict(loc.get("fulfillment") or {})
    preorder = dict(fulfillment.get("preorder") or {})
    compliance = dict(loc.get("compliance") or {})
    payment = dict(loc.get("payment") or {})
    contact = dict(loc.get("contact") or {})
    closed = list(hours.get("closed_dates") or [])
    # Feiertage = zusätzliche Schließtage (ISO-Daten)
    for d in hours.get("holidays") or []:
        ds = str(d).strip()
        if ds and ds not in closed:
            closed.append(ds)
    return {
        "timezone": (loc.get("timezone") or DEFAULT_TZ).strip() or DEFAULT_TZ,
        "hours": {
            "regular": {k: list(regular.get(k) or []) for k in DAY_KEYS},
            "special": list(hours.get("special") or []),
            "closed_dates": closed,
            "holidays": list(hours.get("holidays") or []),
        },
        "fulfillment": {
            "online_ordering": fulfillment.get("online_ordering", True) is not False,
            "pickup": fulfillment.get("pickup", True) is not False,
            "delivery": fulfillment.get("delivery", True) is not False,
            "delivery_fee_eur": float(fulfillment.get("delivery_fee_eur", 2.5)),
            "min_order_delivery_eur": float(fulfillment.get("min_order_delivery_eur", 15.0)),
            "preorder_enabled": bool(preorder.get("enabled", False)),
            "preorder_lead_minutes": int(preorder.get("lead_minutes", 60)),
            "last_order_buffer_minutes": int(fulfillment.get("last_order_buffer_minutes", 15)),
            "slot_interval_minutes": int(fulfillment.get("slot_interval_minutes", 15)),
            "extra_delay_minutes": int(fulfillment.get("extra_delay_minutes", 0)),
        },
        "delivery_zones": list(loc.get("delivery_zones") or []),
        "popular_item_ids": list(loc.get("popular_item_ids") or []),
        "compliance": {
            "require_allergens_for_sale": bool(compliance.get("require_allergens_for_sale", False)),
            "require_additives_for_sale": bool(compliance.get("require_additives_for_sale", False)),
        },
        "payment": {
            "cash": payment.get("cash", True) is not False,
            "card": payment.get("card", True) is not False,
            "card_min_eur": float(payment.get("card_min_eur", 15.0)),
            "stripe": payment.get("stripe", True) is not False,
            "stripe_min_eur": float(payment.get("stripe_min_eur", 0.0)),
        },
        "contact": contact,
        "address": loc.get("address") or {},
    }


def _special_intervals_for_date(special: list[dict], day: date) -> list[list[str]] | None:
    """Wenn ein Sonderöffnungseintrag für day existiert: Intervalle (oder [] = geschlossen).
    None = kein Sonderfall."""
    day_s = day.isoformat()
    for entry in special:
        if not isinstance(entry, dict):
            continue
        if (entry.get("date") or "").strip() != day_s:
            continue
        if entry.get("closed") is True:
            return []
        intervals = entry.get("intervals")
        if intervals is None:
            return []
        return [list(x) for x in intervals]
    return None


def intervals_for(day: date, loc: dict[str, Any]) -> list[list[str]]:
    hours = loc["hours"]
    if day.isoformat() in set(hours.get("closed_dates") or []):
        return []
    special = _special_intervals_for_date(hours.get("special") or [], day)
    if special is not None:
        return special
    key = WEEKDAY_TO_KEY[day.weekday()]
    return list((hours.get("regular") or {}).get(key) or [])


def is_within_hours(now: datetime, loc: dict[str, Any]) -> bool:
    tz = ZoneInfo(loc["timezone"])
    local = now.astimezone(tz) if now.tzinfo else now.replace(tzinfo=tz)
    intervals = intervals_for(local.date(), loc)
    t = local.time().replace(microsecond=0)
    for pair in intervals:
        if len(pair) >= 2 and _in_interval(t, pair[0], pair[1]):
            return True
    return False


def _combine(day: date, hhmm: str, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, _parse_hhmm(hhmm), tzinfo=tz)


def next_open_at(now: datetime, loc: dict[str, Any], *, horizon_days: int = 14) -> datetime | None:
    """Nächster Öffnungsbeginn ab now (inkl. heute später)."""
    tz = ZoneInfo(loc["timezone"])
    local = now.astimezone(tz) if now.tzinfo else now.replace(tzinfo=tz)
    for offset in range(horizon_days + 1):
        day = (local + timedelta(days=offset)).date()
        for pair in intervals_for(day, loc):
            if len(pair) < 2:
                continue
            start = _combine(day, pair[0], tz)
            end = _combine(day, pair[1], tz)
            if offset == 0:
                if local < start:
                    return start
                if start <= local < end:
                    return None  # schon offen
            else:
                return start
    return None


def last_order_deadline(now: datetime, loc: dict[str, Any], prep_minutes: int) -> datetime | None:
    """Spätester Annahmezeitpunkt heute (Ende Intervall − Buffer − Prep)."""
    tz = ZoneInfo(loc["timezone"])
    local = now.astimezone(tz) if now.tzinfo else now.replace(tzinfo=tz)
    buffer_m = int(loc["fulfillment"].get("last_order_buffer_minutes") or 15)
    intervals = intervals_for(local.date(), loc)
    if not intervals:
        return None
    # Aktuelles oder nächstes Intervall heute
    deadline: datetime | None = None
    for pair in intervals:
        if len(pair) < 2:
            continue
        start = _combine(local.date(), pair[0], tz)
        end = _combine(local.date(), pair[1], tz)
        cut = end - timedelta(minutes=buffer_m + max(0, prep_minutes))
        if local < end:
            deadline = cut
            if local >= start:
                break
    return deadline


def settings_flags(settings: dict[str, str] | None) -> dict[str, Any]:
    import time as _t
    s = settings or {}
    online_raw = s.get("online", "1")
    online = str(online_raw).strip() in ("1", "true", "True", "yes")

    # Timed pause: pause_until ist Unix-Timestamp (0 = deaktiviert)
    pause_until_raw = int(s.get("pause_until", "0") or "0")
    pause_until_active = pause_until_raw > 0 and pause_until_raw > _t.time()
    # Unbegrenzte Pause (pause_until=0, aber online=0): bleibt bestehen
    timed_pause_expired = pause_until_raw > 0 and pause_until_raw <= _t.time()
    # Wenn Timer abgelaufen → online wieder true (settings_flags korrigiert den Zustand)
    effective_online = online or timed_pause_expired

    # pause_type: all | instant | delivery | pickup
    pause_type = (s.get("pause_type") or "all").strip().lower()
    valid_pause_types = {"all", "instant", "delivery", "pickup"}
    if pause_type not in valid_pause_types:
        pause_type = "all"

    return {
        "manual_online": effective_online,
        "wait_pickup": int(s.get("wait_pickup", "20") or 20),
        "wait_delivery": int(s.get("wait_delivery", "40") or 40),
        "offline_msg": s.get("offline_msg") or s.get("pause_msg") or "Wir sind gleich zurück!",
        "pause_reason": (s.get("pause_reason") or s.get("pause_msg") or "").strip(),
        "pause_type": pause_type,
        "pause_until": pause_until_raw,
        "pause_until_active": pause_until_active,
        "raw_online": online,
    }


def compute_shop_status(
    *,
    kunde: dict | None,
    settings: dict[str, str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Ein Status für alle Surfaces."""
    loc = load_location_config(kunde)
    flags = settings_flags(settings)
    tz = ZoneInfo(loc["timezone"])
    moment = now or datetime.now(tz)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=tz)
    local = moment.astimezone(tz)

    within = is_within_hours(local, loc)
    pickup_ok = bool(loc["fulfillment"]["pickup"])
    delivery_ok = bool(loc["fulfillment"]["delivery"])
    online_cfg = bool(loc["fulfillment"]["online_ordering"])
    manual_online = bool(flags["manual_online"])
    preorder_enabled = bool(loc["fulfillment"]["preorder_enabled"])
    prep_pickup = int(flags["wait_pickup"])
    prep_delivery = int(flags["wait_delivery"])
    extra_delay = int(loc["fulfillment"].get("extra_delay_minutes") or 0)

    # Manuelle Pause sperrt Online-Bestellung – nicht die Öffnungs-Ampel.
    # Ampel / store_open = Ladentür (Öffnungszeiten).
    # paused / accept_* = Online-Kanal.
    paused = not manual_online
    store_open = within
    pause_type = flags.get("pause_type", "all")
    pause_until_active = flags.get("pause_until_active", False)

    # Cutoff: nach last_order keine Sofortbestellung (Vorbestellung ggf. weiter)
    cutoff = last_order_deadline(local, loc, prep_pickup + extra_delay)
    past_cutoff = bool(cutoff and local >= cutoff and within)
    accept_now = within and not past_cutoff
    accept_online_base = online_cfg and manual_online and (accept_now or preorder_enabled)

    # ── Teilpausen: kanalbezogene Durchsetzung ──────────────────────────────
    #
    # VERBINDLICHE PAUSENREGELN (Stand Pilot-Freigabe):
    #
    # pause_type="all":
    #   Keine neuen Bestellungen jeglicher Art (Sofort + Vorbestellung).
    #   accept_orders=False, accept_pickup=False, accept_delivery=False.
    #
    # pause_type="delivery":
    #   ALLE Lieferbestellungen gesperrt – Sofort UND Vorbestellungen.
    #   Begründung: Liefer-Kapazität ist komplett eingeschränkt während der Pause.
    #   Vorbestellungen für Zeit NACH Pausenende sind ebenfalls gesperrt,
    #   weil die Küche nicht wissen kann, ob die Kapazität danach vorhanden ist.
    #   accept_delivery=False, accept_pickup=True (unverändert)
    #
    # pause_type="pickup":
    #   ALLE Abholbestellungen gesperrt – Sofort UND Vorbestellungen.
    #   accept_pickup=False, accept_delivery=True (unverändert)
    #
    # pause_type="instant":
    #   Nur Sofortbestellungen gesperrt. Vorbestellungen (für später) erlaubt,
    #   sofern preorder_enabled=True.
    #   accept_orders nur für Vorbestellungen, accept_pickup=True (Vorbestellung),
    #   accept_delivery=True (Vorbestellung).
    #
    # Sicherheitsregel: Teilpause gilt nur wenn wirklich aktiv
    # (online=0 ODER pause_until_active). Sonst normaler Betrieb.
    # ─────────────────────────────────────────────────────────────────────────
    actually_paused = paused or pause_until_active

    if not actually_paused:
        # Normaler Betrieb
        accept_online = accept_online_base
        accept_pickup = accept_online and pickup_ok
        accept_delivery = accept_online and delivery_ok
        accept_preorder = accept_online_base and preorder_enabled

    elif pause_type == "delivery":
        # Nur Lieferung pausiert – auch Vorbestellungen als Lieferung geblockt
        accept_online = online_cfg and manual_online and (accept_now or preorder_enabled)
        accept_pickup = accept_online and pickup_ok          # Abholung weiterhin möglich
        accept_delivery = False                              # ALLE Lieferbestellungen geblockt
        accept_preorder = preorder_enabled                   # nur für Abholung relevant

    elif pause_type == "pickup":
        # Nur Abholung pausiert – auch Vorbestellungen als Abholung geblockt
        accept_online = online_cfg and manual_online and (accept_now or preorder_enabled)
        accept_pickup = False                                # ALLE Abholbestellungen geblockt
        accept_delivery = accept_online and delivery_ok      # Lieferung weiterhin möglich
        accept_preorder = preorder_enabled                   # nur für Lieferung relevant

    elif pause_type == "instant":
        # Nur Sofortbestellungen pausiert; Vorbestellungen für später erlaubt
        # accept_now=False gesetzt damit Sofortbestellung nicht möglich
        _accept_now_override = False
        accept_online = online_cfg and manual_online and preorder_enabled
        accept_pickup = accept_online and pickup_ok and preorder_enabled
        accept_delivery = accept_online and delivery_ok and preorder_enabled
        accept_preorder = preorder_enabled                   # explizit erlaubt

    else:
        # "all": alles geblockt
        accept_online = False
        accept_pickup = False
        accept_delivery = False
        accept_preorder = False

    nxt = next_open_at(local, loc)
    next_open_iso = nxt.isoformat(timespec="minutes") if nxt else None
    next_open_label = ""
    if nxt:
        if nxt.date() == local.date():
            next_open_label = f"öffnet heute um {nxt.strftime('%H:%M')}"
        elif nxt.date() == (local + timedelta(days=1)).date():
            next_open_label = f"öffnet morgen um {nxt.strftime('%H:%M')}"
        else:
            days_de = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")
            next_open_label = f"öffnet {days_de[nxt.weekday()]} {nxt.strftime('%H:%M')}"

    reasons: list[str] = []
    if paused:
        reasons.append("manual_pause")
    if not within:
        reasons.append("outside_hours")
    if past_cutoff:
        reasons.append("past_last_order")
    if not online_cfg:
        reasons.append("online_ordering_disabled")

    # Ampel-Label nur aus Öffnungszeiten (nicht aus Online-Pause).
    hours_today = intervals_for(local.date(), loc)
    if within:
        label = "Geöffnet"
    elif not hours_today:
        label = "Ruhetag"
    else:
        label = "Geschlossen"

    summary = " · ".join(f"{a}–{b}" for a, b in hours_today) if hours_today else "Geschlossen"

    return {
        "timezone": loc["timezone"],
        "now_local": local.isoformat(timespec="seconds"),
        "weekday": WEEKDAY_TO_KEY[local.weekday()],
        "store_open": store_open,
        "within_hours": within,
        "past_last_order": past_cutoff,
        "last_order_at": cutoff.isoformat(timespec="minutes") if cutoff else None,
        "next_open_at": next_open_iso,
        "next_open_label": next_open_label,
        "manual_online": manual_online,
        "paused": paused,
        "pause_reason": flags["pause_reason"] or (flags["offline_msg"] if paused else ""),
        "label": label,
        "hours_today": hours_today,
        "hours_today_label": summary,
        "regular_hours": loc["hours"]["regular"],
        "special_hours": loc["hours"]["special"],
        "closed_dates": loc["hours"]["closed_dates"],
        "holidays": loc["hours"].get("holidays") or [],
        "online_ordering_enabled": online_cfg,
        "accept_orders": accept_online,
        "accept_pickup": accept_pickup,
        "accept_delivery": accept_delivery,
        "accept_preorder": accept_preorder,
        "pause_type": pause_type if actually_paused else None,
        "pause_until": flags.get("pause_until", 0),
        "preorder_enabled": preorder_enabled,
        "preorder_lead_minutes": loc["fulfillment"]["preorder_lead_minutes"],
        "wait_pickup": prep_pickup,
        "wait_delivery": prep_delivery,
        "extra_delay_minutes": extra_delay,
        "offline_msg": flags["offline_msg"],
        "fulfillment": {
            "delivery_fee_eur": loc["fulfillment"]["delivery_fee_eur"],
            "min_order_delivery_eur": loc["fulfillment"]["min_order_delivery_eur"],
            "pickup": pickup_ok,
            "delivery": delivery_ok,
            "last_order_buffer_minutes": loc["fulfillment"]["last_order_buffer_minutes"],
            "slot_interval_minutes": loc["fulfillment"]["slot_interval_minutes"],
        },
        "payment": loc["payment"],
        "delivery_zones": loc["delivery_zones"],
        "popular_item_ids": loc["popular_item_ids"],
        "compliance": loc["compliance"],
        "reasons": reasons,
        "kunde_id": (kunde or {}).get("id") or os.getenv("KUNDE_ID") or "",
    }


def item_sale_allowed(item: dict[str, Any], compliance: dict[str, Any]) -> tuple[bool, str]:
    """Compliance-Guard für einzelne Produkte (Allergene/Zusatzstoffe)."""
    if compliance.get("require_allergens_for_sale"):
        allergens = item.get("allergens")
        if not isinstance(allergens, list) or len(allergens) == 0:
            # Explizites leeres Marker-Feld "allergens_declared": true erlaubt Verkauf ohne Allergene
            if not item.get("allergens_declared"):
                return False, "allergens_missing"
    if compliance.get("require_additives_for_sale"):
        additives = item.get("additives")
        if not isinstance(additives, list):
            if not item.get("additives_declared"):
                return False, "additives_missing"
    return True, ""


def filter_sellable_items(
    items: list[dict[str, Any]], compliance: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ok: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for it in items:
        allowed, reason = item_sale_allowed(it, compliance)
        if allowed:
            ok.append(it)
        else:
            blocked.append({**it, "_block_reason": reason})
    return ok, blocked


def assert_orders_accepted(status: dict[str, Any], *, delivery_type: str = "") -> str | None:
    """None wenn OK, sonst Fehlermeldung für API."""
    if not status.get("accept_orders"):
        if status.get("paused"):
            return status.get("offline_msg") or "Online-Bestellung ist gerade ausgeschaltet."
        if status.get("preorder_enabled"):
            return None
        return "Außerhalb der Öffnungszeiten. Bestellung derzeit nicht möglich."
    dt = (delivery_type or "").strip().lower()
    if dt in ("lieferung", "delivery") and not status.get("accept_delivery"):
        return "Lieferung ist derzeit nicht verfügbar."
    if dt in ("abholung", "pickup") and not status.get("accept_pickup"):
        return "Abholung ist derzeit nicht verfügbar."
    return None

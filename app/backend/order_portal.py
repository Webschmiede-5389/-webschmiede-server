# -*- coding: utf-8 -*-
"""Bestellportal-Hilfen: Zeitslots, Liefergebiet, Zahlungsarten, Status-Labels."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import shop_status as ss

# DB-Status → Gast-sichtbare Stufen
STATUS_FLOW = [
    ("neu", "eingegangen", "Bestellung eingegangen"),
    ("angenommen", "angenommen", "Angenommen"),
    ("zubereitung", "in_zubereitung", "In Zubereitung"),
    ("abholbereit", "abholbereit", "Abholbereit"),
    ("unterwegs", "unterwegs", "Unterwegs"),
    ("fertig", "abgeschlossen", "Abgeschlossen"),
    ("storniert", "storniert", "Abgelehnt / storniert"),
]

STATUS_MAP = {db: (guest, label) for db, guest, label in STATUS_FLOW}


def public_status(db_status: str | None) -> dict[str, Any]:
    raw = (db_status or "neu").strip().lower()
    # Legacy: kein separates „angenommen“ → neu = Annahme ausstehend
    if raw == "neu":
        return {
            "code": "neu",
            "stage": "eingegangen",
            "label": "Bestellung eingegangen",
            "awaiting_accept": True,
            "steps": [
                {"id": "eingegangen", "done": True, "current": True, "label": "Eingegangen"},
                {"id": "angenommen", "done": False, "current": False, "label": "Annahme ausstehend"},
                {"id": "in_zubereitung", "done": False, "current": False, "label": "Zubereitung"},
                {"id": "ready", "done": False, "current": False, "label": "Fertig / unterwegs"},
                {"id": "done", "done": False, "current": False, "label": "Abgeschlossen"},
            ],
        }
    guest, label = STATUS_MAP.get(raw, (raw, raw))
    order_keys = ["eingegangen", "angenommen", "in_zubereitung", "ready", "done"]
    mapping = {
        "neu": 0,
        "angenommen": 1,
        "zubereitung": 2,
        "abholbereit": 3,
        "unterwegs": 3,
        "fertig": 4,
        "storniert": -1,
    }
    idx = mapping.get(raw, 0)
    steps = []
    labels = {
        "eingegangen": "Eingegangen",
        "angenommen": "Angenommen",
        "in_zubereitung": "Zubereitung",
        "ready": "Fertig / unterwegs",
        "done": "Abgeschlossen",
    }
    if raw == "storniert":
        return {
            "code": raw,
            "stage": "storniert",
            "label": label,
            "awaiting_accept": False,
            "steps": [{"id": "storniert", "done": True, "current": True, "label": "Storniert"}],
        }
    for i, key in enumerate(order_keys):
        steps.append({
            "id": key,
            "label": labels[key],
            "done": i < idx,
            "current": i == idx,
        })
    return {
        "code": raw,
        "stage": guest,
        "label": label,
        "awaiting_accept": False,
        "steps": steps,
    }


def payment_options(subtotal: float, payment_cfg: dict[str, Any], *, delivery: bool) -> list[dict]:
    out = []
    cash_ok = payment_cfg.get("cash", True) is not False
    out.append({
        "id": "cash",
        "label": "Barzahlung",
        "hint": "bei Abholung oder Lieferung",
        "enabled": cash_ok,
        "reason": "" if cash_ok else "Barzahlung deaktiviert",
    })
    card_min = float(payment_cfg.get("card_min_eur") or 15)
    card_cfg = payment_cfg.get("card", True) is not False
    card_ok = card_cfg and subtotal + 1e-9 >= card_min
    out.append({
        "id": "card",
        "label": "Karte am Lesegerät",
        "hint": f"EC / Kreditkarte ab {card_min:.0f} €",
        "enabled": card_ok,
        "reason": "" if card_ok else (f"ab {card_min:.0f} € Bestellwert" if card_cfg else "Kartenzahlung deaktiviert"),
    })
    stripe_min = float(payment_cfg.get("stripe_min_eur") or 0)
    stripe_cfg = payment_cfg.get("stripe", True) is not False
    stripe_ok = stripe_cfg and subtotal + 1e-9 >= stripe_min
    out.append({
        "id": "stripe",
        "label": "Online (Stripe)",
        "hint": "sichere Online-Zahlung",
        "enabled": stripe_ok,
        "reason": "" if stripe_ok else (f"ab {stripe_min:.0f} €" if stripe_cfg else "Online-Zahlung deaktiviert"),
    })
    return out


def check_delivery_zone(
    *,
    plz: str,
    city: str,
    street: str = "",
    zones: list[dict] | None = None,
) -> dict[str, Any]:
    """Serverseitige Liefergebietsprüfung. Ohne Zonen: PLZ 53894 + Mechernich erlaubt."""
    plz_n = re.sub(r"\D", "", plz or "")[:5]
    city_n = (city or "").strip().lower()
    street_n = (street or "").strip().lower()
    zone_list = zones or []

    if not zone_list:
        # SHY001-Default: Mechernich Kern
        ok = plz_n == "53894" or "mechernich" in city_n
        return {
            "ok": ok,
            "zone_id": "mechernich" if ok else "",
            "fee_eur": 0.0 if ok else None,
            "min_order_eur": 15.0,
            "message": "" if ok else "Leider außerhalb unseres Liefergebiets (Mechernich).",
        }

    for z in zone_list:
        zplz = [str(x) for x in (z.get("plz") or [])]
        cities = [str(c).lower() for c in (z.get("cities") or [])]
        keywords = [str(k).lower() for k in (z.get("street_keywords") or [])]
        match = False
        if plz_n and plz_n in zplz:
            match = True
        if city_n and any(c in city_n or city_n in c for c in cities):
            match = True
        if street_n and any(k in street_n for k in keywords):
            match = True
        if match:
            return {
                "ok": True,
                "zone_id": z.get("id") or "",
                "fee_eur": float(z.get("fee_eur", 0)),
                "min_order_eur": float(z.get("min_order_eur", 15)),
                "message": z.get("label") or "Lieferung möglich",
            }
    return {
        "ok": False,
        "zone_id": "",
        "fee_eur": None,
        "min_order_eur": None,
        "message": "Adresse liegt außerhalb des Liefergebiets.",
    }


def compute_time_slots(
    status: dict[str, Any],
    *,
    order_type: str = "pickup",
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Dynamische Zeitfenster bis Öffnungsende / Cutoff."""
    tz = ZoneInfo(status.get("timezone") or "Europe/Berlin")
    local = now or datetime.now(tz)
    if local.tzinfo is None:
        local = local.replace(tzinfo=tz)
    else:
        local = local.astimezone(tz)

    is_delivery = order_type in ("delivery", "lieferung")
    prep = int(status.get("wait_delivery" if is_delivery else "wait_pickup") or 20)
    extra = int(status.get("extra_delay_minutes") or 0)
    interval = int((status.get("fulfillment") or {}).get("slot_interval_minutes") or 15)
    lead = prep + extra

    slots: list[dict[str, Any]] = []
    if not status.get("accept_orders") and not status.get("preorder_enabled"):
        return slots

    # ASAP
    asap_at = local + timedelta(minutes=lead)
    cutoff_s = status.get("last_order_at")
    cutoff = datetime.fromisoformat(cutoff_s) if cutoff_s else None
    if cutoff and cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=tz)

    def _ok(dt: datetime) -> bool:
        if cutoff and dt > cutoff + timedelta(minutes=lead):
            # Slot nach Küchenschluss
            end_label = status.get("hours_today") or []
            if end_label:
                try:
                    end = datetime.combine(
                        local.date(),
                        ss._parse_hhmm(end_label[-1][1]),
                        tzinfo=tz,
                    )
                    if dt > end:
                        return False
                except Exception:
                    pass
        # Muss in Öffnungsintervall liegen (Ankunft)
        return ss.is_within_hours(dt, {
            "timezone": status["timezone"],
            "hours": {
                "regular": status.get("regular_hours") or {},
                "special": status.get("special_hours") or [],
                "closed_dates": status.get("closed_dates") or [],
            },
            "fulfillment": status.get("fulfillment") or {},
        }) if status.get("regular_hours") else True

    # Fallback-Loc aus Status rekonstruieren für is_within_hours
    loc_min = {
        "timezone": status.get("timezone") or "Europe/Berlin",
        "hours": {
            "regular": status.get("regular_hours") or ss.DEFAULT_REGULAR_HOURS,
            "special": status.get("special_hours") or [],
            "closed_dates": status.get("closed_dates") or [],
        },
        "fulfillment": status.get("fulfillment") or {},
    }

    if status.get("store_open") or status.get("within_hours") or status.get("preorder_enabled"):
        slots.append({
            "id": "asap",
            "label": f"So schnell wie möglich (~{lead} Min.)",
            "at": asap_at.isoformat(timespec="minutes"),
            "minutes_from_now": lead,
        })

    # Gerundete Slots
    cursor = local + timedelta(minutes=lead)
    # aufrunden auf Intervall
    minute = ((cursor.minute // interval) + 1) * interval
    if minute >= 60:
        cursor = cursor.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    else:
        cursor = cursor.replace(minute=minute, second=0, microsecond=0)

    for _ in range(24):
        if not ss.is_within_hours(cursor, loc_min):
            # nächster Tag / nächstes Intervall
            nxt = ss.next_open_at(cursor, loc_min)
            if not nxt:
                break
            cursor = nxt + timedelta(minutes=lead)
            continue
        mins = int((cursor - local).total_seconds() // 60)
        if mins < lead:
            cursor += timedelta(minutes=interval)
            continue
        kind = "Lieferung" if is_delivery else "Abholung"
        clock = cursor.strftime("%H:%M")
        slots.append({
            "id": clock,
            "label": f"{kind} um {clock} Uhr",
            "at": cursor.isoformat(timespec="minutes"),
            "minutes_from_now": mins,
        })
        cursor += timedelta(minutes=interval)
        if len(slots) >= 16:
            break

    # Dedup by id
    seen = set()
    uniq = []
    for s in slots:
        if s["id"] in seen:
            continue
        seen.add(s["id"])
        uniq.append(s)
    return uniq


def build_order_options(status: dict[str, Any], *, order_type: str = "pickup", subtotal: float = 0.0) -> dict[str, Any]:
    delivery = order_type in ("delivery", "lieferung")
    fee = float((status.get("fulfillment") or {}).get("delivery_fee_eur") or 2.5) if delivery else 0.0
    min_o = float((status.get("fulfillment") or {}).get("min_order_delivery_eur") or 15.0) if delivery else 0.0
    return {
        "order_type": "delivery" if delivery else "pickup",
        "wait_minutes": int(status.get("wait_delivery" if delivery else "wait_pickup") or 20)
        + int(status.get("extra_delay_minutes") or 0),
        "delivery_fee_eur": fee,
        "min_order_eur": min_o,
        "accept": bool(status.get("accept_delivery" if delivery else "accept_pickup")),
        "slots": compute_time_slots(status, order_type=order_type),
        "payments": payment_options(subtotal, status.get("payment") or {}, delivery=delivery),
        "shop_status": {
            "label": status.get("label"),
            "store_open": status.get("store_open"),
            "next_open_label": status.get("next_open_label"),
            "accept_orders": status.get("accept_orders"),
        },
    }

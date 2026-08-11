# -*- coding: utf-8 -*-
"""
order_priority.py
-----------------
Serverseitige Prioritätslogik für die Bestellreihenfolge im Dashboard.

Prioritätswerte (kleiner = dringender):
  0  – überfällig: Bestellung sollte schon fertig sein
  10 – Produktionsstart jetzt oder überschritten
  20 – Sofortbestellung (kein Wunschtermin / asap)
  30 – Vorbestellung, Produktionsstart in < 30 min
  40 – Vorbestellung, Abholzeit in < 90 min
  50 – spätere Vorbestellung
  90 – fertig / abholbereit (warten auf Abholung)
  99 – abgeschlossen / storniert / abgelehnt

Regeln:
  - requested_ready_at = vom Kunden gewünschte Abholzeit (aus wunschzeit)
  - production_start_at = max(jetzt, requested_ready_at − wait_pickup)
  - expected_ready_at = vom Mitarbeiter bei Verzögerung gesetzte Zeit
  - Fehlt wunschzeit vollständig → Sofortbestellung (prio 20)
  - Abgeschlossene/stornierte Bestellungen schlagen nicht nach vorne
"""
from __future__ import annotations

import re
import datetime as _dt
from typing import Any

_DONE_STATUSES = frozenset({"fertig", "storniert", "abgelehnt"})
_READY_STATUSES = frozenset({"abholbereit", "unterwegs"})
_ACTIVE_STATUSES = frozenset({"neu", "zubereitung"})

# Standardvorlaufzeit in Minuten bis zur Fertigstellung (Fallback, wenn kein wait_pickup bekannt)
DEFAULT_PREP_MINUTES = 20


def _parse_wunschzeit(wz: str | None) -> _dt.datetime | None:
    """Parst HH:MM oder 'HH:MM Uhr' aus wunschzeit; gibt None zurück wenn nicht parsbar."""
    if not wz:
        return None
    wz = (wz or "").strip()
    asap_markers = {"asap", "so schnell wie möglich", "sofort", ""}
    if wz.lower() in asap_markers:
        return None
    m = re.search(r"(\d{1,2}):(\d{2})", wz)
    if not m:
        return None
    now = _dt.datetime.now()
    try:
        candidate = now.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
        # Falls die Uhrzeit bereits vergangen → nächster Tag
        if candidate < now - _dt.timedelta(hours=12):
            candidate += _dt.timedelta(days=1)
        return candidate
    except ValueError:
        return None


def _parse_iso(s: str | None) -> _dt.datetime | None:
    if not s:
        return None
    try:
        return _dt.datetime.fromisoformat(s)
    except Exception:
        return None


def compute_priority(order: dict[str, Any], wait_pickup_minutes: int = DEFAULT_PREP_MINUTES) -> dict[str, Any]:
    """
    Berechnet Prioritätsscore und annotierte Zeitfelder für eine Bestellung.

    Gibt ein Dict zurück das direkt an die Bestellkarte angehängt werden kann:
      priority_score       int
      priority_label       str  (lesbar)
      requested_ready_at   str | None  (ISO)
      production_start_at  str | None  (ISO)
      is_overdue           bool
      minutes_until_ready  int | None
    """
    status = (order.get("status") or "").strip().lower()
    now = _dt.datetime.now()

    # Abgeschlossene Bestellungen sofort sortieren
    if status in _DONE_STATUSES:
        return {
            "priority_score": 99,
            "priority_label": "Abgeschlossen",
            "requested_ready_at": None,
            "production_start_at": None,
            "is_overdue": False,
            "minutes_until_ready": None,
        }

    if status in _READY_STATUSES:
        # Abholbereit: je länger wartend, desto dringender → aber hinter aktiven Bestellungen
        completed_at = _parse_iso(order.get("completed_at"))
        wait_min = int((now - completed_at).total_seconds() / 60) if completed_at else 0
        return {
            "priority_score": 90,
            "priority_label": f"Wartet auf Abholung ({wait_min} Min)",
            "requested_ready_at": None,
            "production_start_at": None,
            "is_overdue": False,
            "minutes_until_ready": None,
        }

    # Aktive Bestellungen: neu / zubereitung
    wunschzeit = (order.get("wunschzeit") or "").strip()
    requested_ready = _parse_wunschzeit(wunschzeit)

    # Produktion sollte spätestens wait_pickup_minutes vor Wunschzeit beginnen
    if requested_ready:
        production_start = requested_ready - _dt.timedelta(minutes=wait_pickup_minutes)
    else:
        production_start = None

    # expected_ready_at vom Mitarbeiter gesetzte Zeit überschreibt die Pünktlichkeitsbewertung
    expected_ready = _parse_iso(order.get("expected_ready_at"))
    production_started = _parse_iso(order.get("production_started_at"))

    # Überfälligkeitsprüfung
    is_overdue = False
    if status == "zubereitung" and expected_ready and expected_ready < now:
        is_overdue = True
    elif status == "zubereitung" and requested_ready and requested_ready < now and not expected_ready:
        is_overdue = True

    if is_overdue:
        return {
            "priority_score": 0,
            "priority_label": "ÜBERFÄLLIG",
            "requested_ready_at": requested_ready.isoformat() if requested_ready else None,
            "production_start_at": production_start.isoformat() if production_start else None,
            "is_overdue": True,
            "minutes_until_ready": None,
        }

    # Produktionsstart bereits erreicht?
    if production_start and production_start <= now:
        mins_late = int((now - production_start).total_seconds() / 60)
        return {
            "priority_score": 10,
            "priority_label": f"Jetzt starten (Produktionsstart vor {mins_late} Min)",
            "requested_ready_at": requested_ready.isoformat() if requested_ready else None,
            "production_start_at": production_start.isoformat(),
            "is_overdue": False,
            "minutes_until_ready": int((requested_ready - now).total_seconds() / 60) if requested_ready else None,
        }

    # Sofortbestellung (keine Wunschzeit)
    if not requested_ready:
        return {
            "priority_score": 20,
            "priority_label": "Sofortbestellung",
            "requested_ready_at": None,
            "production_start_at": None,
            "is_overdue": False,
            "minutes_until_ready": wait_pickup_minutes,
        }

    # Vorbestellung
    mins_until = int((requested_ready - now).total_seconds() / 60)
    mins_until_prod = int((production_start - now).total_seconds() / 60) if production_start else mins_until

    if mins_until_prod <= 30:
        score = 30
        label = f"Bald starten (in {mins_until_prod} Min)"
    elif mins_until <= 90:
        score = 40
        label = f"Vorbestellung {wunschzeit} (in {mins_until} Min)"
    else:
        score = 50
        label = f"Vorbestellung {wunschzeit} (in {mins_until} Min)"

    return {
        "priority_score": score,
        "priority_label": label,
        "requested_ready_at": requested_ready.isoformat(),
        "production_start_at": production_start.isoformat() if production_start else None,
        "is_overdue": False,
        "minutes_until_ready": mins_until,
    }


def sort_orders(orders: list[dict], wait_pickup_minutes: int = DEFAULT_PREP_MINUTES) -> list[dict]:
    """
    Gibt die Bestellliste mit priority_* Feldern zurück, sortiert nach Priorität.
    Sekundär: bei gleichem Score nach requested_ready_at ASC (frühere zuerst),
    dann nach created_at ASC.
    """
    for o in orders:
        prio = compute_priority(o, wait_pickup_minutes)
        o.update(prio)

    def sort_key(o: dict):
        score = o.get("priority_score", 50)
        ready = o.get("requested_ready_at") or "9999"
        created = o.get("created_at") or "9999"
        return (score, ready, created)

    return sorted(orders, key=sort_key)

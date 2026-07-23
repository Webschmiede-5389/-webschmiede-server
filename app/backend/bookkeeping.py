"""Buchhaltungs-Vorbereitung: Monatsreport & CSV-Export."""
from __future__ import annotations

import csv
import io
import json
import sqlite3
from datetime import date, datetime
from typing import Any


def _month_bounds(year: int, month: int) -> tuple[str, str]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start.isoformat(), end.isoformat()


def _prev_month(today: date | None = None) -> tuple[int, int]:
    d = today or date.today()
    if d.month == 1:
        return d.year - 1, 12
    return d.year, d.month - 1


def fetch_orders(
    db: sqlite3.Connection,
    *,
    date_from: str,
    date_to: str,
) -> list[dict[str, Any]]:
    rows = db.execute(
        """SELECT order_number, created_at, first_name, last_name, phone, email,
                  delivery_type, pay_method, total, status, promo_applied
           FROM orders
           WHERE created_at >= ? AND created_at < ? AND status != 'storniert'
           ORDER BY created_at""",
        (f"{date_from} 00:00:00", f"{date_to} 00:00:00"),
    ).fetchall()
    return [dict(r) for r in rows]


def month_report(db: sqlite3.Connection, *, year: int | None = None, month: int | None = None) -> dict:
    if year is None or month is None:
        year, month = _prev_month()
    date_from, date_to = _month_bounds(year, month)
    orders = fetch_orders(db, date_from=date_from, date_to=date_to)

    total_revenue = 0.0
    cash_total = card_total = other_total = 0.0
    cash_count = card_count = other_count = 0
    delivery_count = pickup_count = 0

    for o in orders:
        total_revenue += float(o["total"] or 0)
        pm = (o.get("pay_method") or "").lower()
        if pm in ("cash", "bar"):
            cash_total += float(o["total"] or 0)
            cash_count += 1
        elif pm in ("card", "ec", "karte"):
            card_total += float(o["total"] or 0)
            card_count += 1
        else:
            other_total += float(o["total"] or 0)
            other_count += 1
        if o.get("delivery_type") == "lieferung":
            delivery_count += 1
        else:
            pickup_count += 1

    return {
        "year": year,
        "month": month,
        "period_from": date_from,
        "period_to_exclusive": date_to,
        "order_count": len(orders),
        "total_revenue": round(total_revenue, 2),
        "cash_total": round(cash_total, 2),
        "cash_count": cash_count,
        "card_total": round(card_total, 2),
        "card_count": card_count,
        "other_total": round(other_total, 2),
        "other_count": other_count,
        "delivery_count": delivery_count,
        "pickup_count": pickup_count,
    }


def orders_csv(db: sqlite3.Connection, *, date_from: str, date_to: str) -> str:
    orders = fetch_orders(db, date_from=date_from, date_to=date_to)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\n")
    w.writerow([
        "Datum", "Bestellnr", "Name", "Telefon", "E-Mail",
        "Art", "Zahlart", "Betrag_EUR", "Status", "Aktion",
    ])
    for o in orders:
        name = f"{o.get('first_name', '')} {o.get('last_name', '')}".strip()
        w.writerow([
            (o.get("created_at") or "")[:19],
            o.get("order_number") or "",
            name,
            o.get("phone") or "",
            o.get("email") or "",
            o.get("delivery_type") or "",
            o.get("pay_method") or "",
            f"{float(o.get('total') or 0):.2f}".replace(".", ","),
            o.get("status") or "",
            o.get("promo_applied") or "",
        ])
    return buf.getvalue()

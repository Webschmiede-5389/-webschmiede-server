"""Handwerk: Anfragen / Jobs (Maler, Bau, …)."""
from __future__ import annotations

import csv
import io
import re
import sqlite3
from datetime import date, datetime
from typing import Any

STATUSES = ("neu", "termin", "angebot", "erledigt", "storniert")
PAY_METHODS = ("bar", "ec", "ueberweisung", "offen")


def ensure_table(db: sqlite3.Connection) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            ref          TEXT UNIQUE,
            created_at   TEXT DEFAULT (datetime('now')),
            updated_at   TEXT DEFAULT (datetime('now')),
            customer_name TEXT NOT NULL,
            phone        TEXT,
            email        TEXT,
            plz          TEXT,
            address      TEXT,
            subject      TEXT,
            description  TEXT,
            status       TEXT DEFAULT 'neu',
            amount_eur   REAL,
            pay_method   TEXT DEFAULT 'offen',
            completed_at TEXT,
            notes        TEXT,
            source       TEXT DEFAULT 'form'
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at)")


def _new_ref(db: sqlite3.Connection) -> str:
    day = datetime.now().strftime("%Y%m%d")
    prefix = f"J-{day}-"
    row = db.execute(
        "SELECT ref FROM jobs WHERE ref LIKE ? ORDER BY ref DESC LIMIT 1",
        (prefix + "%",),
    ).fetchone()
    n = 1
    if row and row["ref"]:
        m = re.search(r"-(\d+)$", row["ref"])
        if m:
            n = int(m.group(1)) + 1
    return f"{prefix}{n:03d}"


def create_job(db: sqlite3.Connection, data: dict) -> dict:
    ensure_table(db)
    name = (data.get("customer_name") or data.get("name") or "").strip()
    if not name:
        raise ValueError("Name fehlt")
    ref = _new_ref(db)
    cur = db.execute(
        """INSERT INTO jobs
           (ref, customer_name, phone, email, plz, address, subject, description,
            status, amount_eur, pay_method, notes, source)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            ref,
            name[:120],
            (data.get("phone") or "")[:40] or None,
            (data.get("email") or "")[:120] or None,
            (data.get("plz") or "")[:12] or None,
            (data.get("address") or "")[:200] or None,
            (data.get("subject") or "")[:200] or None,
            (data.get("description") or data.get("message") or "")[:2000] or None,
            (data.get("status") or "neu").lower(),
            float(data["amount_eur"]) if data.get("amount_eur") not in (None, "") else None,
            (data.get("pay_method") or "offen").lower(),
            (data.get("notes") or "")[:2000] or None,
            (data.get("source") or "form")[:40],
        ),
    )
    db.commit()
    return get_job(db, cur.lastrowid) or {}


def list_jobs(db: sqlite3.Connection, *, status: str | None = None, limit: int = 200) -> list[dict]:
    ensure_table(db)
    q = "SELECT * FROM jobs WHERE 1=1"
    params: list[Any] = []
    if status and status != "alle":
        q += " AND status=?"
        params.append(status)
    q += " ORDER BY CASE status WHEN 'neu' THEN 0 WHEN 'termin' THEN 1 WHEN 'angebot' THEN 2 ELSE 9 END, updated_at DESC LIMIT ?"
    params.append(limit)
    return [dict(r) for r in db.execute(q, params).fetchall()]


def get_job(db: sqlite3.Connection, job_id: int) -> dict | None:
    ensure_table(db)
    row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    return dict(row) if row else None


def update_job(db: sqlite3.Connection, job_id: int, data: dict) -> dict | None:
    ensure_table(db)
    job = get_job(db, job_id)
    if not job:
        return None

    status = (data.get("status") or job["status"]).lower()
    if status not in STATUSES:
        raise ValueError("Ungültiger Status")

    amount = data.get("amount_eur", job.get("amount_eur"))
    if amount in ("", None):
        amount_val = None
    else:
        amount_val = float(amount)

    pay = (data.get("pay_method") or job.get("pay_method") or "offen").lower()
    completed_at = job.get("completed_at")
    if status == "erledigt" and not completed_at:
        completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if status != "erledigt":
        completed_at = data.get("completed_at") if "completed_at" in data else None

    db.execute(
        """UPDATE jobs SET
           customer_name=?, phone=?, email=?, plz=?, address=?, subject=?, description=?,
           status=?, amount_eur=?, pay_method=?, completed_at=?, notes=?,
           updated_at=datetime('now')
           WHERE id=?""",
        (
            (data.get("customer_name") or job["customer_name"])[:120],
            (data.get("phone") if "phone" in data else job.get("phone") or "")[:40] or None,
            (data.get("email") if "email" in data else job.get("email") or "")[:120] or None,
            (data.get("plz") if "plz" in data else job.get("plz") or "")[:12] or None,
            (data.get("address") if "address" in data else job.get("address") or "")[:200] or None,
            (data.get("subject") if "subject" in data else job.get("subject") or "")[:200] or None,
            (data.get("description") if "description" in data else job.get("description") or "")[:2000] or None,
            status,
            amount_val,
            pay,
            completed_at,
            (data.get("notes") if "notes" in data else job.get("notes") or "")[:2000] or None,
            job_id,
        ),
    )
    db.commit()
    return get_job(db, job_id)


def _month_bounds(year: int, month: int) -> tuple[str, str]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start.isoformat(), end.isoformat()


def prev_month(today: date | None = None) -> tuple[int, int]:
    d = today or date.today()
    if d.month == 1:
        return d.year - 1, 12
    return d.year, d.month - 1


def fetch_completed(
    db: sqlite3.Connection,
    *,
    date_from: str,
    date_to: str,
) -> list[dict]:
    ensure_table(db)
    rows = db.execute(
        """SELECT * FROM jobs
           WHERE status='erledigt'
             AND completed_at >= ? AND completed_at < ?
           ORDER BY completed_at""",
        (f"{date_from} 00:00:00", f"{date_to} 00:00:00"),
    ).fetchall()
    return [dict(r) for r in rows]


def month_report(db: sqlite3.Connection, *, year: int | None = None, month: int | None = None) -> dict:
    if year is None or month is None:
        year, month = prev_month()
    date_from, date_to = _month_bounds(year, month)
    jobs = fetch_completed(db, date_from=date_from, date_to=date_to)

    total = cash = card = transfer = 0.0
    cash_n = card_n = transfer_n = 0
    for j in jobs:
        amt = float(j.get("amount_eur") or 0)
        total += amt
        pm = (j.get("pay_method") or "").lower()
        if pm == "bar":
            cash += amt
            cash_n += 1
        elif pm in ("ec", "karte", "card"):
            card += amt
            card_n += 1
        elif pm == "ueberweisung":
            transfer += amt
            transfer_n += 1

    open_count = db.execute(
        "SELECT COUNT(*) AS c FROM jobs WHERE status IN ('neu','termin','angebot')"
    ).fetchone()["c"]

    return {
        "year": year,
        "month": month,
        "period_from": date_from,
        "period_to_exclusive": date_to,
        "job_count_completed": len(jobs),
        "jobs_open": open_count,
        "total_revenue": round(total, 2),
        "cash_total": round(cash, 2),
        "cash_count": cash_n,
        "card_total": round(card, 2),
        "card_count": card_n,
        "transfer_total": round(transfer, 2),
        "transfer_count": transfer_n,
    }


def jobs_csv(db: sqlite3.Connection, *, date_from: str, date_to: str) -> str:
    jobs = fetch_completed(db, date_from=date_from, date_to=date_to)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\n")
    w.writerow([
        "Erledigt_am", "Referenz", "Kunde", "Telefon", "PLZ", "Betreff",
        "Betrag_EUR", "Zahlart", "Notizen",
    ])
    for j in jobs:
        w.writerow([
            (j.get("completed_at") or "")[:19],
            j.get("ref") or "",
            j.get("customer_name") or "",
            j.get("phone") or "",
            j.get("plz") or "",
            j.get("subject") or "",
            f"{float(j.get('amount_eur') or 0):.2f}".replace(".", ","),
            j.get("pay_method") or "",
            (j.get("notes") or "")[:200],
        ])
    return buf.getvalue()

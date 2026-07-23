"""Agency KPIs, Events und tägliche Metriken."""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta


def ensure_schema(db: sqlite3.Connection) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS ops_events (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT (datetime('now')),
            kunde_id   TEXT,
            category   TEXT NOT NULL,
            action     TEXT NOT NULL,
            status     TEXT NOT NULL,
            detail     TEXT,
            meta       TEXT
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS ops_metrics_daily (
            day        TEXT NOT NULL,
            kunde_id   TEXT NOT NULL DEFAULT '',
            metric     TEXT NOT NULL,
            value      REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (day, kunde_id, metric)
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_ops_events_created ON ops_events(created_at)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_ops_events_kunde ON ops_events(kunde_id)")


def record_event(
    db: sqlite3.Connection,
    *,
    category: str,
    action: str,
    status: str = "ok",
    kunde_id: str = "",
    detail: str = "",
    meta: dict | None = None,
) -> None:
    ensure_schema(db)
    db.execute(
        """INSERT INTO ops_events (kunde_id, category, action, status, detail, meta)
           VALUES (?,?,?,?,?,?)""",
        (
            (kunde_id or "").upper()[:32],
            category[:40],
            action[:80],
            status[:20],
            (detail or "")[:500],
            json.dumps(meta or {}, ensure_ascii=False)[:2000],
        ),
    )


def bump_daily(db: sqlite3.Connection, metric: str, *, kunde_id: str = "", amount: float = 1.0) -> None:
    ensure_schema(db)
    day = date.today().isoformat()
    kid = (kunde_id or "").upper()[:32]
    db.execute(
        """INSERT INTO ops_metrics_daily (day, kunde_id, metric, value)
           VALUES (?,?,?,?)
           ON CONFLICT(day, kunde_id, metric) DO UPDATE SET value = value + excluded.value""",
        (day, kid, metric[:60], float(amount)),
    )


def get_kpis(db: sqlite3.Connection, *, days: int = 7, kunde_id: str = "") -> dict:
    ensure_schema(db)
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    kid = (kunde_id or "").upper()

    orders_today = db.execute(
        "SELECT COUNT(*) FROM orders WHERE date(created_at)=date('now')"
    ).fetchone()[0]

    sms_sent = db.execute(
        "SELECT COUNT(*) FROM message_log WHERE channel='sms' AND status='sent' AND created_at >= ?",
        (since,),
    ).fetchone()[0]
    sms_failed = db.execute(
        "SELECT COUNT(*) FROM message_log WHERE channel='sms' AND (status LIKE 'fail%' OR status='error') AND created_at >= ?",
        (since,),
    ).fetchone()[0]

    return {
        "period_days": days,
        "orders_today": int(orders_today),
        "orders_period": int(
            db.execute(
                "SELECT COUNT(*) FROM orders WHERE created_at >= ?",
                (since,),
            ).fetchone()[0]
        ),
        "sms_sent": int(sms_sent),
        "sms_failed": int(sms_failed),
        "bot_messages": int(
            db.execute(
                "SELECT COUNT(*) FROM bot_log WHERE created_at >= ?",
                (since,),
            ).fetchone()[0]
        ),
        "integration_errors": int(
            db.execute(
                "SELECT COUNT(*) FROM ops_events WHERE status='error' AND created_at >= ?",
                (since,),
            ).fetchone()[0]
        ),
        "events_error_24h": int(
            db.execute(
                "SELECT COUNT(*) FROM ops_events WHERE status IN ('error','critical') "
                "AND created_at >= datetime('now','-1 day')",
            ).fetchone()[0]
        ),
    }


def recent_events(db: sqlite3.Connection, *, limit: int = 30, kunde_id: str = "") -> list[dict]:
    ensure_schema(db)
    if kunde_id:
        rows = db.execute(
            "SELECT * FROM ops_events WHERE kunde_id=? ORDER BY id DESC LIMIT ?",
            (kunde_id.upper(), limit),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM ops_events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]

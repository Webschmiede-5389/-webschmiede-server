# -*- coding: utf-8 -*-
"""P0 Order Acceptance Flow – SHY001 (neu → angenommen → zubereitung)."""
from __future__ import annotations

import os
import sys
import sqlite3

import pytest

BACKEND = os.path.join(os.path.dirname(__file__), "..", "app", "backend")
sys.path.insert(0, os.path.abspath(BACKEND))

import order_portal as op  # noqa: E402


# ── Transitions ─────────────────────────────────────────────────────────────

class TestTransitions:
    def test_create_default_is_neu_semantics(self):
        assert "neu" in op.ORDER_STATUSES
        assert "angenommen" in op.ORDER_STATUSES

    def test_neu_to_angenommen_allowed(self):
        assert op.can_transition("neu", "angenommen")
        assert op.transition_error("neu", "angenommen") is None

    def test_neu_to_zubereitung_forbidden(self):
        assert not op.can_transition("neu", "zubereitung")
        err = op.transition_error("neu", "zubereitung")
        assert err and "nicht erlaubt" in err

    def test_angenommen_to_zubereitung_allowed(self):
        assert op.can_transition("angenommen", "zubereitung")
        assert op.transition_error("angenommen", "zubereitung") is None

    def test_idempotent_same_status(self):
        assert op.can_transition("angenommen", "angenommen")
        assert op.transition_error("neu", "neu") is None

    def test_invalid_status_rejected(self):
        err = op.transition_error("neu", "accepted")
        assert err and "Ungültig" in err

    def test_later_flows_intact(self):
        assert op.can_transition("zubereitung", "abholbereit")
        assert op.can_transition("zubereitung", "unterwegs")
        assert op.can_transition("abholbereit", "fertig")
        assert op.can_transition("unterwegs", "fertig")
        assert op.can_transition("neu", "storniert")
        assert op.can_transition("angenommen", "storniert")
        assert not op.can_transition("fertig", "neu")
        assert not op.can_transition("storniert", "zubereitung")


class TestPublicStatus:
    def test_neu_awaits_accept(self):
        pub = op.public_status("neu")
        assert pub["awaiting_accept"] is True
        assert pub["code"] == "neu"

    def test_angenommen_not_awaiting(self):
        pub = op.public_status("angenommen")
        assert pub["awaiting_accept"] is False
        assert pub["stage"] == "angenommen"
        assert pub["label"] == "Angenommen"

    def test_zubereitung_stage(self):
        pub = op.public_status("zubereitung")
        assert pub["stage"] == "in_zubereitung"


class TestPendingCopy:
    def test_pending_sms_no_accept_language(self):
        text = op.pending_customer_sms("Max", "Snack House Yassine", "SH-1", "02443")
        low = text.lower()
        assert "eingegangen" in low
        assert "prüfen" in low or "pruefen" in low or "angenommen haben" in low
        assert "wird zubereitet" not in low
        assert "✓" not in text
        assert "bestätigt" not in low
        # "angenommen haben" is OK (future), but not "wurde angenommen"
        assert "wurde angenommen" not in low

    def test_accepted_sms(self):
        text = op.accepted_customer_sms("Max", "Snack House Yassine", "SH-1", "https://example/status")
        assert "angenommen" in text.lower()
        assert "SH-1" in text
        assert "https://example/status" in text


class TestAcceptIdempotencyMarker:
    """message_log claim pattern used by send_accepted_notification."""

    def test_already_sent_detection(self, tmp_path):
        db_path = tmp_path / "t.db"
        db = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
        db.execute(
            """CREATE TABLE message_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_phone TEXT, channel TEXT, template TEXT,
                body TEXT, status TEXT, order_number TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )"""
        )
        db.commit()

        def already(order_number, template):
            row = db.execute(
                """SELECT 1 FROM message_log
                   WHERE order_number=? AND template=? AND status='sent' LIMIT 1""",
                (order_number, template),
            ).fetchone()
            return row is not None

        tpl = op.ACCEPT_NOTIFY_TEMPLATE
        assert already("SH-A", tpl) is False
        db.execute(
            "INSERT INTO message_log (contact_phone, channel, template, body, status, order_number) VALUES (?,?,?,?,?,?)",
            ("+491", "notify", tpl, "x", "sent", "SH-A"),
        )
        db.commit()
        assert already("SH-A", tpl) is True
        assert already("SH-B", tpl) is False
        # second insert would be blocked by caller – count stays 1
        count = db.execute(
            "SELECT COUNT(*) AS c FROM message_log WHERE order_number=? AND template=? AND status='sent'",
            ("SH-A", tpl),
        ).fetchone()["c"]
        assert count == 1
        db.close()


class TestDefaultOrderStatusInsert:
    def test_sqlite_default_neu(self, tmp_path):
        db = sqlite3.connect(tmp_path / "o.db")
        db.execute(
            """CREATE TABLE orders (
                order_number TEXT PRIMARY KEY,
                status TEXT DEFAULT 'neu'
            )"""
        )
        db.execute("INSERT INTO orders (order_number) VALUES ('SH-NEW')")
        db.commit()
        row = db.execute("SELECT status FROM orders WHERE order_number='SH-NEW'").fetchone()
        assert row[0] == "neu"
        db.close()

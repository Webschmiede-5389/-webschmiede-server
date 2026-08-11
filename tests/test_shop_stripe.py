# -*- coding: utf-8 -*-
"""SHY001 Shop Stripe Batch-2 – Unit tests (TEST MODE, mocked Stripe)."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

BACKEND = Path(__file__).resolve().parents[1] / "app" / "backend"
sys.path.insert(0, str(BACKEND))

import shop_stripe as ss  # noqa: E402
import order_portal as op  # noqa: E402


@pytest.fixture()
def db():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute(
        """CREATE TABLE orders (
            order_number TEXT PRIMARY KEY,
            status TEXT DEFAULT 'neu',
            pay_method TEXT,
            total REAL,
            email TEXT,
            payment_status TEXT,
            stripe_checkout_session_id TEXT,
            stripe_payment_intent_id TEXT,
            payment_refund_required INTEGER DEFAULT 0
        )"""
    )
    ss.ensure_schema(con)
    yield con
    con.close()


def _insert(db, **kw):
    defaults = {
        "order_number": "SH-T-1",
        "status": "neu",
        "pay_method": "cash",
        "total": 12.5,
        "email": "t@example.com",
        "payment_status": ss.PS_UNPAID,
        "stripe_checkout_session_id": None,
        "stripe_payment_intent_id": None,
        "payment_refund_required": 0,
    }
    defaults.update(kw)
    cols = ",".join(defaults.keys())
    qs = ",".join("?" for _ in defaults)
    db.execute(f"INSERT INTO orders ({cols}) VALUES ({qs})", tuple(defaults.values()))
    db.commit()
    return dict(db.execute("SELECT * FROM orders WHERE order_number=?", (defaults["order_number"],)).fetchone())


class TestCashNoStripe:
    def test_cash_default_unpaid(self):
        assert ss.default_payment_status("cash") == ss.PS_UNPAID

    def test_cash_does_not_create_session(self, db):
        order = _insert(db, pay_method="cash", payment_status=ss.PS_UNPAID)
        with pytest.raises(ValueError, match="pay_method=stripe"):
            ss.create_or_reuse_checkout_session(db, order=order)


class TestCheckoutSession:
    @patch.dict(os.environ, {"SHOP_STRIPE_SECRET_KEY": "sk_test_x"}, clear=False)
    @patch("shop_stripe.stripe.checkout.Session.create")
    def test_online_creates_session(self, mock_create, db):
        mock_create.return_value = MagicMock(id="cs_test_1", url="https://checkout.stripe.com/c/pay/cs_test_1")
        order = _insert(db, pay_method="stripe", payment_status=ss.PS_PENDING, total=15.0)
        out = ss.create_or_reuse_checkout_session(db, order=order)
        assert out["url"].startswith("https://checkout.stripe.com")
        assert out["session_id"] == "cs_test_1"
        assert out["amount_cents"] == 1500
        call_kw = mock_create.call_args.kwargs
        assert call_kw["mode"] == "payment"
        assert call_kw["metadata"]["order_number"] == "SH-T-1"
        assert call_kw["idempotency_key"] == "shy001_checkout_SH-T-1"
        row = dict(db.execute("SELECT * FROM orders WHERE order_number='SH-T-1'").fetchone())
        assert row["stripe_checkout_session_id"] == "cs_test_1"
        assert row["payment_status"] == ss.PS_PENDING
        assert row["status"] == "neu"

    def test_server_amount_cents(self):
        assert ss.amount_cents(12.34) == 1234
        with pytest.raises(ValueError):
            ss.amount_cents(0.01)


class TestWebhook:
    def test_invalid_signature_rejected(self, db):
        with patch.dict(os.environ, {"SHOP_STRIPE_WEBHOOK_SECRET": "whsec_test"}, clear=False):
            with patch("shop_stripe.stripe.Webhook.construct_event", side_effect=Exception("bad")):
                # use SignatureVerificationError path
                import stripe as stripe_mod

                with patch(
                    "shop_stripe.stripe.Webhook.construct_event",
                    side_effect=stripe_mod.error.SignatureVerificationError("bad", "sig"),
                ):
                    with pytest.raises(ValueError, match="Signatur"):
                        ss.handle_webhook(db, b"{}", "bad")

    @patch.dict(os.environ, {"SHOP_STRIPE_WEBHOOK_SECRET": "whsec_test"}, clear=False)
    def test_checkout_completed_sets_paid_keeps_neu(self, db):
        _insert(db, pay_method="stripe", payment_status=ss.PS_PENDING, status="neu")
        event = {
            "id": "evt_1",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_1",
                    "payment_status": "paid",
                    "client_reference_id": "SH-T-1",
                    "metadata": {"order_number": "SH-T-1"},
                    "payment_intent": "pi_1",
                }
            },
        }
        with patch("shop_stripe.construct_event", return_value=event):
            r = ss.handle_webhook(db, b"{}", "sig")
        assert r["ok"] is True
        row = dict(db.execute("SELECT * FROM orders WHERE order_number='SH-T-1'").fetchone())
        assert row["payment_status"] == ss.PS_PAID
        assert row["status"] == "neu"
        assert row["stripe_payment_intent_id"] == "pi_1"

    @patch.dict(os.environ, {"SHOP_STRIPE_WEBHOOK_SECRET": "whsec_test"}, clear=False)
    def test_duplicate_event_idempotent(self, db):
        _insert(db, pay_method="stripe", payment_status=ss.PS_PENDING)
        event = {
            "id": "evt_dup",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_1",
                    "payment_status": "paid",
                    "metadata": {"order_number": "SH-T-1"},
                    "payment_intent": "pi_1",
                }
            },
        }
        with patch("shop_stripe.construct_event", return_value=event):
            r1 = ss.handle_webhook(db, b"{}", "sig")
            r2 = ss.handle_webhook(db, b"{}", "sig")
        assert r1.get("changed") or r1.get("ok")
        assert r2.get("duplicate") is True
        n = db.execute("SELECT COUNT(*) FROM shop_stripe_events WHERE event_id='evt_dup'").fetchone()[0]
        assert n == 1

    @patch.dict(os.environ, {"SHOP_STRIPE_WEBHOOK_SECRET": "whsec_test"}, clear=False)
    def test_expired_not_paid(self, db):
        _insert(db, pay_method="stripe", payment_status=ss.PS_PENDING)
        event = {
            "id": "evt_exp",
            "type": "checkout.session.expired",
            "data": {"object": {"id": "cs_x", "metadata": {"order_number": "SH-T-1"}}},
        }
        with patch("shop_stripe.construct_event", return_value=event):
            ss.handle_webhook(db, b"{}", "sig")
        row = dict(db.execute("SELECT * FROM orders WHERE order_number='SH-T-1'").fetchone())
        assert row["payment_status"] == ss.PS_FAILED
        assert row["status"] == "neu"

    @patch.dict(os.environ, {"SHOP_STRIPE_WEBHOOK_SECRET": "whsec_test"}, clear=False)
    def test_payment_failed(self, db):
        _insert(db, pay_method="stripe", payment_status=ss.PS_PENDING)
        event = {
            "id": "evt_fail",
            "type": "payment_intent.payment_failed",
            "data": {"object": {"metadata": {"order_number": "SH-T-1"}}},
        }
        with patch("shop_stripe.construct_event", return_value=event):
            ss.handle_webhook(db, b"{}", "sig")
        row = dict(db.execute("SELECT * FROM orders WHERE order_number='SH-T-1'").fetchone())
        assert row["payment_status"] == ss.PS_FAILED
        assert row["status"] == "neu"


class TestPaidReject:
    def test_refund_required_flag(self, db):
        _insert(db, pay_method="stripe", payment_status=ss.PS_PAID, status="neu")
        assert ss.mark_refund_required(db, "SH-T-1") is True
        row = dict(db.execute("SELECT * FROM orders WHERE order_number='SH-T-1'").fetchone())
        assert row["payment_refund_required"] == 1
        assert "REFUND" in ss.payment_label(row)


class TestAcceptanceIntact:
    def test_transitions_still_ok(self):
        assert op.can_transition("neu", "angenommen")
        assert not op.can_transition("neu", "zubereitung")
        assert op.can_transition("angenommen", "zubereitung")

    def test_paid_order_can_be_accepted(self, db):
        _insert(db, pay_method="stripe", payment_status=ss.PS_PAID, status="neu")
        assert op.can_transition("neu", "angenommen")
        # simulate accept without touching payment
        db.execute("UPDATE orders SET status='angenommen' WHERE order_number='SH-T-1'")
        db.commit()
        row = dict(db.execute("SELECT * FROM orders WHERE order_number='SH-T-1'").fetchone())
        assert row["status"] == "angenommen"
        assert row["payment_status"] == ss.PS_PAID


class TestLabels:
    def test_cash_label(self):
        assert ss.payment_label({"pay_method": "cash", "payment_status": "unpaid"}) == "BARZAHLUNG"

    def test_paid_label(self):
        assert ss.payment_label({"pay_method": "stripe", "payment_status": "paid"}) == "ONLINE BEZAHLT"

# -*- coding: utf-8 -*-
"""SHY001 Shop Stripe Checkout (einmalige Zahlungen) – getrennt von Agency stripe_billing."""
from __future__ import annotations

import logging
import os
from typing import Any

import stripe

log = logging.getLogger(__name__)

# Fachliche Payment-Zustände (orders.payment_status)
PS_UNPAID = "unpaid"
PS_PENDING = "pending"
PS_PAID = "paid"
PS_FAILED = "failed"
PS_REFUNDED = "refunded"

VALID_PAYMENT_STATUSES = frozenset(
    {PS_UNPAID, PS_PENDING, PS_PAID, PS_FAILED, PS_REFUNDED}
)


def ensure_schema(db) -> None:
    """Soft-Migration: Payment-/Stripe-Spalten + Event-Idempotenz (ADD COLUMN Pattern)."""
    for col, typ in [
        ("payment_status", "TEXT"),
        ("stripe_checkout_session_id", "TEXT"),
        ("stripe_payment_intent_id", "TEXT"),
        ("payment_refund_required", "INTEGER DEFAULT 0"),
    ]:
        try:
            db.execute(f"ALTER TABLE orders ADD COLUMN {col} {typ}")
        except Exception:
            pass
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS shop_stripe_events (
            event_id TEXT PRIMARY KEY,
            event_type TEXT,
            order_number TEXT,
            processed_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    try:
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_orders_stripe_session "
            "ON orders(stripe_checkout_session_id)"
        )
    except Exception:
        pass


def shop_stripe_configured() -> bool:
    return bool(_secret_key())


def _secret_key() -> str:
    # Shop-Keys zuerst – Agency STRIPE_SECRET_KEY bewusst nicht mischen
    return (
        os.getenv("SHOP_STRIPE_SECRET_KEY", "").strip()
        or os.getenv("STRIPE_SHOP_SECRET_KEY", "").strip()
    )


def _webhook_secret() -> str:
    return (
        os.getenv("SHOP_STRIPE_WEBHOOK_SECRET", "").strip()
        or os.getenv("STRIPE_SHOP_WEBHOOK_SECRET", "").strip()
    )


def _mode() -> str:
    return (os.getenv("SHOP_STRIPE_MODE") or "test").strip().lower()


def _configure() -> None:
    key = _secret_key()
    if not key:
        raise RuntimeError("SHOP_STRIPE_SECRET_KEY fehlt")
    stripe.api_key = key


def public_base_url() -> str:
    base = (
        os.getenv("SHOP_PUBLIC_BASE_URL", "").strip()
        or os.getenv("PUBLIC_BASE_URL", "").strip()
        or "https://snackhouse-yassine.de"
    )
    return base.rstrip("/")


def amount_cents(total_eur: float) -> int:
    cents = int(round(float(total_eur) * 100))
    if cents < 50:
        raise ValueError("Betrag zu niedrig für Stripe Checkout (min. 0,50 €)")
    return cents


def default_payment_status(pay_method: str) -> str:
    pm = (pay_method or "").strip().lower()
    if pm == "stripe":
        return PS_PENDING
    return PS_UNPAID


def payment_label(order: dict) -> str:
    """Dashboard/Bon-Label."""
    ps = (order.get("payment_status") or "").strip().lower()
    pm = (order.get("pay_method") or "").strip().lower()
    if order.get("payment_refund_required"):
        return "ONLINE BEZAHLT – REFUND ERFORDERLICH"
    if ps == PS_PAID or (pm == "stripe" and ps == PS_PAID):
        return "ONLINE BEZAHLT"
    if pm == "stripe" and ps == PS_PENDING:
        return "ONLINE-ZAHLUNG AUSSTEHEND"
    if pm == "stripe" and ps == PS_FAILED:
        return "ONLINE-ZAHLUNG FEHLGESCHLAGEN"
    if pm == "card":
        return "EC-KARTE VOR ORT"
    if pm == "cash" or ps == PS_UNPAID:
        return "BARZAHLUNG"
    return (pm or "ZAHLUNG").upper()


def create_or_reuse_checkout_session(
    db,
    *,
    order: dict,
    kunde_id: str = "SHY001",
) -> dict[str, Any]:
    """Checkout Session für bestehende Order. Idempotent je order_number."""
    order_number = (order.get("order_number") or "").strip()
    if not order_number:
        raise ValueError("order_number fehlt")
    if (order.get("pay_method") or "").lower() != "stripe":
        raise ValueError("Checkout nur für pay_method=stripe")
    _configure()

    existing = (order.get("stripe_checkout_session_id") or "").strip()
    if existing and (order.get("payment_status") or "") == PS_PAID:
        raise ValueError("Bestellung ist bereits bezahlt")

    if existing:
        try:
            sess = stripe.checkout.Session.retrieve(existing)
            if sess.get("status") in ("open",) and sess.get("url"):
                return {
                    "session_id": sess["id"],
                    "url": sess["url"],
                    "reused": True,
                    "amount_cents": sess.get("amount_total"),
                }
        except Exception as e:
            log.warning("shop_stripe reuse session failed: %s", e)

    total = float(order.get("total") or 0)
    cents = amount_cents(total)
    base = public_base_url()
    success = (
        f"{base}/bestellen?pay=success&nr={order_number}"
        f"&session_id={{CHECKOUT_SESSION_ID}}"
    )
    cancel = f"{base}/bestellen?pay=cancel&nr={order_number}"

    idem_key = f"shy001_checkout_{order_number}"[:255]
    session = stripe.checkout.Session.create(
        mode="payment",
        currency="eur",
        client_reference_id=order_number,
        customer_email=(order.get("email") or None) or None,
        metadata={
            "order_number": order_number,
            "kunde_id": kunde_id,
            "shop": "snackhouse_yassine",
            "purpose": "shop_order",
        },
        line_items=[
            {
                "price_data": {
                    "currency": "eur",
                    "unit_amount": cents,
                    "product_data": {
                        "name": f"Bestellung {order_number}",
                        "description": "Snack House Yassine · Onlinezahlung",
                    },
                },
                "quantity": 1,
            }
        ],
        success_url=success,
        cancel_url=cancel,
        payment_intent_data={
            "metadata": {
                "order_number": order_number,
                "kunde_id": kunde_id,
                "purpose": "shop_order",
            }
        },
        idempotency_key=idem_key,
    )

    db.execute(
        """UPDATE orders SET
               stripe_checkout_session_id=?,
               payment_status=?
           WHERE order_number=?""",
        (session.id, PS_PENDING, order_number),
    )
    db.commit()

    return {
        "session_id": session.id,
        "url": session.url,
        "reused": False,
        "amount_cents": cents,
    }


def construct_event(payload: bytes, sig_header: str):
    secret = _webhook_secret()
    if not secret:
        raise RuntimeError("SHOP_STRIPE_WEBHOOK_SECRET fehlt")
    return stripe.Webhook.construct_event(payload, sig_header, secret)


def event_already_processed(db, event_id: str) -> bool:
    row = db.execute(
        "SELECT 1 FROM shop_stripe_events WHERE event_id=? LIMIT 1",
        (event_id,),
    ).fetchone()
    return row is not None


def mark_event_processed(db, event_id: str, event_type: str, order_number: str = "") -> None:
    db.execute(
        """INSERT OR IGNORE INTO shop_stripe_events (event_id, event_type, order_number)
           VALUES (?,?,?)""",
        (event_id, event_type, order_number or ""),
    )
    db.commit()


def apply_checkout_completed(db, session_obj: dict) -> dict[str, Any]:
    """checkout.session.completed → payment_status=paid, order_status unverändert."""
    meta = session_obj.get("metadata") or {}
    order_number = (
        (meta.get("order_number") or "").strip()
        or (session_obj.get("client_reference_id") or "").strip()
    )
    session_id = session_obj.get("id") or ""
    if not order_number and session_id:
        row = db.execute(
            "SELECT order_number FROM orders WHERE stripe_checkout_session_id=?",
            (session_id,),
        ).fetchone()
        if row:
            order_number = row["order_number"] if hasattr(row, "keys") else row[0]

    if not order_number:
        return {"ok": False, "error": "order_number fehlt in Session"}

    row = db.execute(
        "SELECT * FROM orders WHERE order_number=?", (order_number,)
    ).fetchone()
    if not row:
        return {"ok": False, "error": "order not found", "order_number": order_number}

    order = dict(row)
    # Idempotent: schon paid → no-op (kein Status-Change, keine Extra-Notify hier)
    if (order.get("payment_status") or "").lower() == PS_PAID:
        return {
            "ok": True,
            "unchanged": True,
            "order_number": order_number,
            "payment_status": PS_PAID,
            "order_status": order.get("status"),
        }

    pi = session_obj.get("payment_intent")
    if isinstance(pi, dict):
        pi = pi.get("id")
    pi = (pi or "").strip() or None

    db.execute(
        """UPDATE orders SET
               payment_status=?,
               stripe_checkout_session_id=COALESCE(NULLIF(stripe_checkout_session_id,''), ?),
               stripe_payment_intent_id=COALESCE(?, stripe_payment_intent_id)
           WHERE order_number=?""",
        (PS_PAID, session_id, pi, order_number),
    )
    db.commit()

    # Absolute Regel: order status bleibt wie er ist (typisch neu)
    refreshed = dict(
        db.execute("SELECT status, payment_status FROM orders WHERE order_number=?", (order_number,)).fetchone()
    )
    return {
        "ok": True,
        "order_number": order_number,
        "payment_status": refreshed.get("payment_status"),
        "order_status": refreshed.get("status"),
        "changed": True,
    }


def apply_checkout_expired_or_failed(db, session_obj: dict, *, failed: bool = False) -> dict:
    meta = session_obj.get("metadata") or {}
    order_number = (
        (meta.get("order_number") or "").strip()
        or (session_obj.get("client_reference_id") or "").strip()
    )
    session_id = session_obj.get("id") or ""
    if not order_number and session_id:
        row = db.execute(
            "SELECT order_number FROM orders WHERE stripe_checkout_session_id=?",
            (session_id,),
        ).fetchone()
        if row:
            order_number = row["order_number"] if hasattr(row, "keys") else row[0]
    if not order_number:
        return {"ok": False, "error": "order_number fehlt"}

    row = db.execute("SELECT payment_status, status FROM orders WHERE order_number=?", (order_number,)).fetchone()
    if not row:
        return {"ok": False, "error": "order not found"}
    order = dict(row)
    if (order.get("payment_status") or "").lower() == PS_PAID:
        return {"ok": True, "unchanged": True, "order_number": order_number}

    new_ps = PS_FAILED if failed else PS_FAILED  # expired → failed/pending; mark failed for clarity
    db.execute(
        "UPDATE orders SET payment_status=? WHERE order_number=? AND payment_status != ?",
        (new_ps, order_number, PS_PAID),
    )
    db.commit()
    return {"ok": True, "order_number": order_number, "payment_status": new_ps, "order_status": order.get("status")}


def mark_refund_required(db, order_number: str) -> bool:
    """PAID + Ablehnung → Refund-Hinweis (kein Auto-Refund)."""
    row = db.execute(
        "SELECT payment_status FROM orders WHERE order_number=?",
        (order_number,),
    ).fetchone()
    if not row:
        return False
    ps = (row["payment_status"] if hasattr(row, "keys") else row[0]) or ""
    if ps.lower() != PS_PAID:
        return False
    db.execute(
        "UPDATE orders SET payment_refund_required=1 WHERE order_number=?",
        (order_number,),
    )
    db.commit()
    return True


def handle_webhook(db, payload: bytes, sig_header: str) -> dict[str, Any]:
    """Signatur prüfen, Events idempotent verarbeiten. Ändert nie order status zu angenommen."""
    try:
        event = construct_event(payload, sig_header)
    except stripe.error.SignatureVerificationError as e:
        raise ValueError("Ungültige Stripe-Signatur") from e

    event_id = event.get("id") or ""
    etype = event.get("type") or ""
    if event_id and event_already_processed(db, event_id):
        return {"ok": True, "duplicate": True, "event_id": event_id, "type": etype}

    obj = (event.get("data") or {}).get("object") or {}
    result: dict[str, Any] = {"ok": True, "type": etype, "event_id": event_id}

    if etype == "checkout.session.completed":
        # Nur paid sessions (async methods may complete unpaid – check payment_status)
        pay_status = (obj.get("payment_status") or "").lower()
        if pay_status and pay_status != "paid":
            result["ignored"] = f"payment_status={pay_status}"
        else:
            result.update(apply_checkout_completed(db, obj))
    elif etype == "checkout.session.expired":
        result.update(apply_checkout_expired_or_failed(db, obj, failed=True))
    elif etype == "payment_intent.payment_failed":
        meta = obj.get("metadata") or {}
        order_number = (meta.get("order_number") or "").strip()
        if order_number:
            row = db.execute(
                "SELECT payment_status FROM orders WHERE order_number=?",
                (order_number,),
            ).fetchone()
            if row and (dict(row).get("payment_status") or "").lower() != PS_PAID:
                db.execute(
                    "UPDATE orders SET payment_status=? WHERE order_number=?",
                    (PS_FAILED, order_number),
                )
                db.commit()
                result["order_number"] = order_number
                result["payment_status"] = PS_FAILED
        else:
            result["ignored"] = "no order_number"
    else:
        result["ignored"] = etype

    if event_id:
        mark_event_processed(
            db,
            event_id,
            etype,
            order_number=str(result.get("order_number") or ""),
        )
    return result

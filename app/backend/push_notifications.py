# -*- coding: utf-8 -*-
"""Web Push für Gäste (Bestellportal) – kostenlos, ohne SMS."""
from __future__ import annotations

import json
import os
from typing import Any

PUSH_ENABLED = os.getenv("PUSH_ENABLED", "true").lower() in ("1", "true", "yes")
VAPID_PRIVATE_KEY = (os.getenv("VAPID_PRIVATE_KEY") or "").strip()
VAPID_PUBLIC_KEY = (os.getenv("VAPID_PUBLIC_KEY") or "").strip()
VAPID_CLAIMS_EMAIL = (os.getenv("VAPID_CLAIMS_EMAIL") or "mailto:info@digitalehandwerkskunst.de").strip()
SHOP_NAME = os.getenv("SHOP_NAME", "Snack House Yassine")


def _private_key() -> str:
    key = VAPID_PRIVATE_KEY
    if "\\n" in key:
        return key.replace("\\n", "\n")
    return key


def config() -> dict[str, Any]:
    ok = PUSH_ENABLED and bool(VAPID_PRIVATE_KEY) and bool(VAPID_PUBLIC_KEY)
    return {
        "enabled": PUSH_ENABLED,
        "configured": ok,
        "public_key": VAPID_PUBLIC_KEY if ok else "",
    }


def init_push_table(db) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS push_subscriptions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT NOT NULL,
            endpoint     TEXT NOT NULL UNIQUE,
            p256dh       TEXT NOT NULL,
            auth         TEXT NOT NULL,
            created_at   TEXT DEFAULT (datetime('now'))
        )
    """)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_push_sub_order ON push_subscriptions(order_number)"
    )


def _order_recent(db, order_number: str) -> bool:
    row = db.execute(
        """SELECT 1 FROM orders
           WHERE order_number=? AND created_at >= datetime('now', '-48 hours')""",
        (order_number.strip(),),
    ).fetchone()
    return row is not None


def subscribe(db, order_number: str, subscription: dict) -> dict[str, Any]:
    if not config()["configured"]:
        return {"ok": False, "error": "Push ist auf dem Server noch nicht eingerichtet (VAPID-Keys fehlen)."}
    order_number = (order_number or "").strip()
    if not order_number:
        return {"ok": False, "error": "Bestellnummer fehlt"}
    if not _order_recent(db, order_number):
        return {"ok": False, "error": "Bestellung unbekannt oder älter als 48 Stunden"}

    endpoint = (subscription.get("endpoint") or "").strip()
    keys = subscription.get("keys") or {}
    p256dh = (keys.get("p256dh") or "").strip()
    auth = (keys.get("auth") or "").strip()
    if not endpoint or not p256dh or not auth:
        return {"ok": False, "error": "Ungültige Push-Daten"}

    db.execute(
        """INSERT INTO push_subscriptions (order_number, endpoint, p256dh, auth)
           VALUES (?,?,?,?)
           ON CONFLICT(endpoint) DO UPDATE SET
             order_number=excluded.order_number,
             p256dh=excluded.p256dh,
             auth=excluded.auth""",
        (order_number, endpoint, p256dh, auth),
    )
    return {"ok": True, "order_number": order_number}


def _subscriptions_for_order(db, order_number: str) -> list[dict]:
    rows = db.execute(
        "SELECT endpoint, p256dh, auth FROM push_subscriptions WHERE order_number=?",
        (order_number,),
    ).fetchall()
    return [dict(r) for r in rows]


def send_to_order(
    db,
    order_number: str,
    *,
    title: str,
    body: str,
    tag: str = "",
    url: str = "",
) -> dict[str, Any]:
    if not config()["configured"]:
        return {"ok": False, "sent": 0, "skipped": "not_configured"}

    subs = _subscriptions_for_order(db, order_number)
    if not subs:
        return {"ok": True, "sent": 0, "skipped": "no_subscribers"}

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        return {"ok": False, "error": "pywebpush nicht installiert", "sent": 0}

    payload = json.dumps(
        {"title": title, "body": body, "tag": tag or order_number, "url": url},
        ensure_ascii=False,
    )
    vapid = {"private_key": VAPID_PRIVATE_KEY, "public_key": VAPID_PUBLIC_KEY}
    sent = 0
    dead: list[str] = []

    for sub in subs:
        subscription = {
            "endpoint": sub["endpoint"],
            "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
        }
        try:
            webpush(
                subscription_info=subscription,
                data=payload,
                vapid_private_key=_private_key(),
                vapid_claims={"sub": VAPID_CLAIMS_EMAIL},
            )
            sent += 1
        except WebPushException as ex:
            status = getattr(ex, "response", None)
            code = status.status_code if status is not None else 0
            if code in (404, 410):
                dead.append(sub["endpoint"])
            else:
                import logging
                logging.getLogger(__name__).warning(
                    "push failed order=%s code=%s %s", order_number, code, ex
                )
        except Exception as ex:
            import logging
            logging.getLogger(__name__).warning("push error order=%s %s", order_number, ex)

    for ep in dead:
        db.execute("DELETE FROM push_subscriptions WHERE endpoint=?", (ep,))

    return {"ok": True, "sent": sent, "removed": len(dead)}


def notify_order_created(db, order: dict) -> None:
    name = order.get("first_name") or "du"
    send_to_order(
        db,
        order["order_number"],
        title=f"{SHOP_NAME}",
        body=f"Hallo {name}! Bestellung {order['order_number']} ist eingegangen.",
        tag=f"order-{order['order_number']}-neu",
    )


def notify_status(db, order: dict, new_status: str) -> None:
    name = order.get("first_name") or "du"
    msgs = {
        "zubereitung": (f"{SHOP_NAME}", f"Hey {name}! Deine Bestellung wird gerade zubereitet."),
        "unterwegs": (f"{SHOP_NAME}", "Auf dem Weg! Ca. 15–25 Minuten."),
        "abholbereit": (f"{SHOP_NAME}", "Abholbereit! Deine Bestellung wartet auf dich."),
        "fertig": (f"{SHOP_NAME}", f"Danke {name}! Wir hoffen, es hat geschmeckt."),
    }
    if new_status not in msgs:
        return
    title, body = msgs[new_status]
    send_to_order(
        db,
        order["order_number"],
        title=title,
        body=body,
        tag=f"order-{order['order_number']}-{new_status}",
    )

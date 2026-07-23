"""Online loyalty stamps (phone = customer ID, no QR)."""
import json

DEFAULT_STAMPS_NEEDED = 10


def get_settings(db) -> dict:
    rows = db.execute("SELECT key, value FROM settings").fetchall()
    s = {r["key"]: r["value"] for r in rows}
    return {
        "enabled": s.get("loyalty_enabled", "1") == "1",
        "stamps_needed": max(2, int(s.get("loyalty_stamps_needed", str(DEFAULT_STAMPS_NEEDED)) or DEFAULT_STAMPS_NEEDED)),
        "reward_item_id": s.get("loyalty_reward_item_id", "g3") or "g3",
        "reward_name": s.get("loyalty_reward_name", "Ayran 0,4 L") or "Gratis-Getränk",
    }


def _contact_stamps(db, phone: str) -> int:
    if not phone:
        return 0
    row = db.execute("SELECT loyalty_stamps FROM contacts WHERE phone=?", (phone,)).fetchone()
    if not row:
        row = db.execute(
            "SELECT loyalty_stamps FROM contacts WHERE phone LIKE ?",
            (f"%{phone[-9:]}",),
        ).fetchone()
    return int(row["loyalty_stamps"]) if row else 0


def status_for_phone(db, phone: str) -> dict | None:
    cfg = get_settings(db)
    if not cfg["enabled"]:
        return {"enabled": False}

    stamps = _contact_stamps(db, phone)
    needed = cfg["stamps_needed"]
    remaining = max(0, needed - 1 - stamps)
    reward_available = stamps >= needed - 1

    if reward_available:
        msg = f"Deine {needed}. Bestellung: {cfg['reward_name']} ist gratis!"
    elif stamps == 0:
        msg = f"Sammle {needed - 1} Stempel, dann gibt's {cfg['reward_name']} gratis!"
    else:
        msg = f"Noch {remaining} Bestellung{'en' if remaining != 1 else ''} bis zu deinem Gratis-Getränk!"

    return {
        "enabled": True,
        "stamps": stamps,
        "needed": needed,
        "remaining": remaining,
        "reward_available": reward_available,
        "reward_item_id": cfg["reward_item_id"],
        "reward_name": cfg["reward_name"],
        "message": msg,
    }


def find_loyalty_free(items: list) -> dict | None:
    for it in items:
        if it.get("loyalty") or it.get("id") == "__loyalty_free__":
            return it
    return None


def validate_loyalty_items(db, phone: str, items: list) -> str | None:
    cfg = get_settings(db)
    if not cfg["enabled"]:
        if find_loyalty_free(items):
            return "Treueprogramm ist deaktiviert"
        return None

    loyalty_items = [it for it in items if it.get("loyalty") or it.get("free") and it.get("id") in (cfg["reward_item_id"], "__loyalty_free__")]
    loyalty_free = [it for it in items if it.get("loyalty")]

    if len(loyalty_free) > 1:
        return "Nur ein Treue-Geschenk pro Bestellung"

    if not loyalty_free:
        return None

    if not phone:
        return "Telefonnummer für Treueprogramm erforderlich"

    stamps = _contact_stamps(db, phone)
    if stamps < cfg["stamps_needed"] - 1:
        return "Treue-Belohnung noch nicht verfügbar"

    item = loyalty_free[0]
    if item.get("id") not in (cfg["reward_item_id"], "__loyalty_free__"):
        return "Ungültiger Treue-Artikel"
    if float(item.get("price") or 0) != 0:
        return "Ungültiger Treue-Preis"

    return None


def apply_after_order(db, phone: str, order_number: str, items: list) -> dict:
    """Update stamps after successful order. Returns summary for API response."""
    cfg = get_settings(db)
    if not cfg["enabled"] or not phone:
        return {"enabled": False}

    had_reward = find_loyalty_free(items) is not None
    stamps_before = _contact_stamps(db, phone)
    needed = cfg["stamps_needed"]

    if had_reward:
        new_stamps = 0
        redeemed = True
    else:
        new_stamps = min(stamps_before + 1, needed - 1)
        redeemed = False

    db.execute(
        "UPDATE contacts SET loyalty_stamps=? WHERE phone=?",
        (new_stamps, phone),
    )
    if db.execute("SELECT changes()").fetchone()[0] == 0:
        db.execute(
            "UPDATE contacts SET loyalty_stamps=? WHERE phone LIKE ?",
            (new_stamps, f"%{phone[-9:]}"),
        )

    db.execute(
        "UPDATE orders SET loyalty_reward=? WHERE order_number=?",
        (1 if had_reward else 0, order_number),
    )

    st = status_for_phone(db, phone)
    return {
        "enabled": True,
        "stamps_before": stamps_before,
        "stamps_after": new_stamps,
        "redeemed": redeemed,
        "needed": needed,
        "reward_name": cfg["reward_name"],
        "message": st["message"] if st else "",
        "reward_available_next": new_stamps >= needed - 1,
    }

"""Server-side order total validation against menu prices."""
import json
import os

from loyalty import validate_loyalty_items

DELIVERY_FEE = 2.50
MIN_ORDER_DELIVERY = 15.00
PRICE_TOLERANCE = 0.06

_prices_cache: dict | None = None


def _load_prices() -> dict:
    global _prices_cache
    if _prices_cache is not None:
        return _prices_cache
    path = os.path.join(os.path.dirname(__file__), "..", "jarvis", "menu_prices.json")
    try:
        with open(path, encoding="utf-8") as f:
            _prices_cache = json.load(f)
    except (OSError, json.JSONDecodeError):
        _prices_cache = {}
    return _prices_cache


def _menu_overrides(db) -> dict:
    rows = db.execute("SELECT * FROM menu_overrides").fetchall()
    out = {}
    for r in rows:
        out[r["item_id"]] = dict(r)
    return out


def _price_ok(item_id: str, price: float, overrides: dict, catalog: dict) -> bool:
    ov = overrides.get(item_id) or {}
    if ov.get("available") == 0:
        return False
    if ov.get("price") is not None:
        return abs(float(ov["price"]) - price) <= PRICE_TOLERANCE
    allowed = catalog.get(item_id)
    if not allowed:
        return 0 < price <= 500
    return any(abs(float(p) - price) <= PRICE_TOLERANCE for p in allowed)


def validate_order_prices(db, data: dict) -> str | None:
    """Returns error message or None."""
    settings = {r["key"]: r["value"] for r in db.execute("SELECT key, value FROM settings").fetchall()}
    if settings.get("online", "1") != "1":
        return "Bestellungen sind gerade nicht möglich."

    items = data.get("items") or []
    delivery = data.get("deliveryType") == "lieferung"
    catalog = _load_prices()
    overrides = _menu_overrides(db)

    subtotal = 0.0
    loyalty_free = 0
    other_free = 0
    for it in items:
        price = float(it.get("price") or 0)
        qty = int(it.get("qty") or 0)
        if qty < 1 or qty > 20:
            return "Ungültige Artikelmenge"
        is_free = bool(it.get("free"))
        is_loyalty = bool(it.get("loyalty"))
        item_id = (it.get("id") or "").strip()

        if is_free or is_loyalty:
            if price != 0:
                return "Ungültiger Gratis-Artikel"
            if is_loyalty:
                loyalty_free += 1
            else:
                other_free += 1
            continue

        if not item_id:
            return "Artikel-ID fehlt"
        if not _price_ok(item_id, price, overrides, catalog):
            return "Preis oder Verfügbarkeit ungültig"
        subtotal += price * qty

    if loyalty_free > 1:
        return "Zu viele Treue-Geschenke"
    if other_free > 1:
        return "Zu viele Gratis-Artikel"
    if loyalty_free + other_free > 2:
        return "Zu viele Gratis-Artikel"

    phone = (data.get("phone") or "").strip()
    loyalty_err = validate_loyalty_items(db, phone, items)
    if loyalty_err:
        return loyalty_err

    if delivery and subtotal < MIN_ORDER_DELIVERY:
        return f"Mindestbestellwert Lieferung: {MIN_ORDER_DELIVERY:.2f} €"

    fee = DELIVERY_FEE if delivery else 0.0
    expected = round(subtotal + fee, 2)
    client_total = round(float(data.get("total") or 0), 2)
    if abs(expected - client_total) > PRICE_TOLERANCE:
        return "Gesamtbetrag stimmt nicht überein"

    return None

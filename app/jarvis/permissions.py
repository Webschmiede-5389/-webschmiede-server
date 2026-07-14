"""Kunden-Zuordnung und Berechtigungen für Jarvis-Bot."""
import json
import os
import re

KUNDEN_DIR = os.getenv(
    "KUNDEN_DIR",
    os.path.join(os.path.dirname(__file__), "..", "kunden"),
)

ALL_PERMISSIONS = frozenset({
    "menu_price", "menu_text", "menu_image", "menu_available", "opening_hours",
})

def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0") and len(digits) >= 10:
        digits = "49" + digits[1:]
    return digits


def _phones_match(a: str, b: str) -> bool:
    da, db = normalize_phone(a), normalize_phone(b)
    if not da or not db:
        return False
    return da == db or da.endswith(db[-9:]) or db.endswith(da[-9:])


def load_clients() -> list[dict]:
    clients = []
    if not os.path.isdir(KUNDEN_DIR):
        return clients
    for fname in sorted(os.listdir(KUNDEN_DIR)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(KUNDEN_DIR, fname)
        try:
            with open(path, encoding="utf-8") as f:
                clients.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            continue
    return clients


def client_by_id(client_id: str) -> dict | None:
    cid = (client_id or "").upper()
    for c in load_clients():
        if c.get("id", "").upper() == cid:
            return c
    return None


def client_by_phone(phone: str) -> dict | None:
    for c in load_clients():
        wa = c.get("whatsapp") or {}
        if not wa.get("enabled", True):
            continue
        for allowed in wa.get("allowed_phones") or []:
            if _phones_match(phone, allowed):
                return c
        kontakt = c.get("kontakt") or {}
        if kontakt.get("telefon") and _phones_match(phone, kontakt["telefon"]):
            return c
    return None


def has_permission(client: dict, perm: str) -> bool:
    wa = client.get("whatsapp") or {}
    perms = wa.get("permissions") or list(ALL_PERMISSIONS)
    blocked = set(wa.get("blocked") or [])
    if perm in blocked:
        return False
    return perm in perms or "admin" in perms


def default_client_id() -> str:
    clients = load_clients()
    return clients[0]["id"] if clients else "SHY001"

"""Jarvis Bot – Nachrichten verarbeiten (Test + WhatsApp)."""
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime

from . import parser
from .permissions import (
    ALL_PERMISSIONS,
    client_by_id,
    client_by_phone,
    has_permission,
    load_clients,
    normalize_phone,
)

CATALOG_PATH = os.path.join(os.path.dirname(__file__), "menu_catalog.json")


def load_catalog() -> list[dict]:
    try:
        with open(CATALOG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return []


def log_bot(db, client_id: str, phone: str, channel: str, direction: str,
            body: str, result: str, meta: dict | None = None):
    db.execute(
        """INSERT INTO bot_log (client_id, phone, channel, direction, body, result, meta)
           VALUES (?,?,?,?,?,?,?)""",
        (client_id, phone, channel, direction, body[:2000], result[:500],
         json.dumps(meta or {}, ensure_ascii=False)),
    )


def get_menu_override(db, item_id: str) -> dict:
    row = db.execute(
        "SELECT * FROM menu_overrides WHERE item_id=?", (item_id,),
    ).fetchone()
    return dict(row) if row else {}


def upsert_menu_override(db, item_id: str, **fields):
    cur = get_menu_override(db, item_id)
    available = fields.get("available", cur.get("available", 1))
    note = fields.get("note", cur.get("note") or "")
    price = fields.get("price", cur.get("price"))
    name = fields.get("name", cur.get("name"))
    desc = fields.get("desc", cur.get("desc"))
    image_url = fields.get("image_url", cur.get("image_url"))
    db.execute(
        """INSERT INTO menu_overrides
           (item_id, available, note, price, name, desc, image_url)
           VALUES (?,?,?,?,?,?,?)
           ON CONFLICT(item_id) DO UPDATE SET
             available=excluded.available, note=excluded.note,
             price=excluded.price, name=excluded.name,
             desc=excluded.desc, image_url=excluded.image_url""",
        (item_id, int(available) if available is not None else 1,
         note, price, name, desc, image_url),
    )


def _upload_dir() -> str:
    return os.getenv(
        "JARVIS_UPLOAD_DIR",
        os.path.join(os.path.dirname(__file__), "..", "uploads", "menu"),
    )


def save_image(image_bytes: bytes, client_id: str, ext: str = "jpg") -> str:
    upload_dir = _upload_dir()
    os.makedirs(upload_dir, exist_ok=True)
    safe_ext = re.sub(r"[^a-z0-9]", "", (ext or "jpg").lower())[:4] or "jpg"
    fname = f"{client_id.lower()}_{uuid.uuid4().hex[:12]}.{safe_ext}"
    path = os.path.join(upload_dir, fname)
    with open(path, "wb") as f:
        f.write(image_bytes)
    return f"/uploads/menu/{fname}"


def handle_message(
    db,
    phone: str,
    text: str = "",
    *,
    client_id: str | None = None,
    image_bytes: bytes | None = None,
    image_ext: str = "jpg",
    channel: str = "test",
    is_agency: bool = False,
) -> dict:
    """Verarbeitet eine eingehende Nachricht. Gibt Antwort-Dict zurück."""
    text = (text or "").strip()
    catalog = load_catalog()
    client = None

    if client_id:
        client = client_by_id(client_id)
    if not client and phone:
        client = client_by_phone(phone)

    if is_agency:
        cmd = parser.parse_admin_command(text)
        if cmd and cmd["action"] == "register_phone":
            return _register_phone(cmd["client_id"], cmd["phone"])
        if not client and client_id:
            client = client_by_id(client_id)

    if not client:
        reply = (
            "Hallo! Diese Nummer ist noch nicht freigeschaltet. "
            "Bitte wende dich an Webschmiede."
        )
        log_bot(db, client_id or "", phone, channel, "in", text, "denied", {"reason": "unknown_client"})
        db.commit()
        return {"success": False, "reply": reply, "error": "unknown_client"}

    cid = client["id"]
    actions = []

    if not text and not image_bytes:
        reply = (
            f"Hallo {client.get('inhaber', client.get('name', ''))}! "
            "Schick mir z.B.:\n"
            "• „Lahmacun-Rolle 7,50 €“\n"
            "• „Margherita ausverkauft“\n"
            "• Foto + Gerichtname"
        )
        log_bot(db, cid, phone, channel, "in", text, "help", {})
        db.commit()
        return {"success": True, "reply": reply, "client_id": cid, "actions": []}

    item = parser.find_item(text, catalog)
    price = parser.parse_price(text)
    desc = parser.parse_description(text)
    avail = parser.parse_availability(text)

    if not item and image_bytes and text:
        item = parser.find_item(text, catalog)

    if not item and not is_agency:
        try:
            from .knowledge import resolve_knowledge, find_faq_answer

            knowledge = resolve_knowledge(client)
            faq = find_faq_answer(knowledge, text)
            if faq and faq.get("answer"):
                reply = faq["answer"]
                log_bot(
                    db, cid, phone, channel, "in", text, "faq",
                    {"faq_id": faq.get("id"), "pack": knowledge.get("pack_id")},
                )
                db.commit()
                return {
                    "success": True,
                    "reply": reply,
                    "client_id": cid,
                    "faq_id": faq.get("id"),
                }
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("knowledge FAQ: %s", exc)
        reply = (
            "Welches Gericht meinst du? Nenne den Namen, z.B. „Lahmacun-Rolle“ "
            "oder „Pizza Margherita“."
        )
        log_bot(db, cid, phone, channel, "in", text, "no_item", {})
        db.commit()
        return {"success": False, "reply": reply, "client_id": cid}

    if item:
        iid = item["id"]
        updates = {}

        if price is not None:
            if not has_permission(client, "menu_price"):
                reply = "Preisänderungen sind für deinen Zugang nicht freigeschaltet."
                log_bot(db, cid, phone, channel, "in", text, "denied_price", {})
                db.commit()
                return {"success": False, "reply": reply, "client_id": cid}
            updates["price"] = price
            actions.append(f"price:{iid}={price}")

        if desc:
            if not has_permission(client, "menu_text"):
                reply = "Textänderungen sind für deinen Zugang nicht freigeschaltet."
                log_bot(db, cid, phone, channel, "in", text, "denied_text", {})
                db.commit()
                return {"success": False, "reply": reply, "client_id": cid}
            updates["desc"] = desc
            actions.append(f"desc:{iid}")

        if avail is not None:
            if not has_permission(client, "menu_available"):
                reply = "Verfügbarkeit ändern ist nicht freigeschaltet."
                log_bot(db, cid, phone, channel, "in", text, "denied_avail", {})
                db.commit()
                return {"success": False, "reply": reply, "client_id": cid}
            updates["available"] = 1 if avail else 0
            actions.append(f"available:{iid}={avail}")

        if image_bytes:
            if not has_permission(client, "menu_image"):
                reply = "Bild-Upload ist für deinen Zugang nicht freigeschaltet."
                log_bot(db, cid, phone, channel, "in", text, "denied_image", {})
                db.commit()
                return {"success": False, "reply": reply, "client_id": cid}
            url = save_image(image_bytes, cid, image_ext)
            updates["image_url"] = url
            actions.append(f"image:{iid}")

        if updates:
            upsert_menu_override(db, iid, **updates)
            parts = [f"✓ {item['name']}"]
            if "price" in updates:
                parts.append(f"Preis: {updates['price']:.2f} €")
            if "desc" in updates:
                parts.append("Beschreibung aktualisiert")
            if "available" in updates:
                parts.append("wieder verfügbar" if updates["available"] else "als ausverkauft markiert")
            if "image_url" in updates:
                parts.append("Bild gespeichert")
            reply = "\n".join(parts) + "\n\nLive auf der Bestellseite."
        else:
            reply = (
                f"Gericht erkannt: {item['name']} ({item['id']}). "
                "Was soll ich ändern? Preis, Text, Bild oder „ausverkauft“?"
            )

        log_bot(db, cid, phone, channel, "in", text, "ok", {"item_id": iid, "actions": actions})
        db.commit()
        return {"success": True, "reply": reply, "client_id": cid, "item_id": iid, "actions": actions}

    reply = "Befehl nicht erkannt."
    log_bot(db, cid, phone, channel, "in", text, "unknown", {})
    db.commit()
    return {"success": False, "reply": reply, "client_id": cid}


def _register_phone(client_id: str, phone: str) -> dict:
    """Agency: Telefonnummer in kunden-JSON eintragen (nur lokal auf Server)."""
    from .permissions import KUNDEN_DIR
    clients = load_clients()
    client = next((c for c in clients if c.get("id") == client_id), None)
    if not client:
        return {"success": False, "reply": f"Kunde {client_id} nicht gefunden."}
    wa = client.setdefault("whatsapp", {
        "enabled": True,
        "allowed_phones": [],
        "permissions": list(ALL_PERMISSIONS - {"opening_hours"}),
        "blocked": ["code", "domain", "admin_password"],
    })
    phones = wa.setdefault("allowed_phones", [])
    norm = normalize_phone(phone)
    if not any(normalize_phone(p) == norm for p in phones):
        phones.append(phone.strip())
    fname = None
    for f in os.listdir(KUNDEN_DIR):
        if f.startswith(client_id) and f.endswith(".json"):
            fname = f
            break
    if fname:
        path = os.path.join(KUNDEN_DIR, fname)
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(client, fp, ensure_ascii=False, indent=2)
    return {
        "success": True,
        "reply": f"✓ {phone} für {client_id} freigeschaltet.",
        "client_id": client_id,
    }


def parse_whatsapp_payload(payload: dict) -> list[dict]:
    """Meta WhatsApp Cloud API → normalisierte Nachrichten."""
    out = []
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            val = change.get("value") or {}
            for msg in val.get("messages") or []:
                mtype = msg.get("type")
                phone = (msg.get("from") or "").strip()
                text = ""
                image_id = None
                if mtype == "text":
                    text = (msg.get("text") or {}).get("body") or ""
                elif mtype == "image":
                    text = (msg.get("image") or {}).get("caption") or ""
                    image_id = (msg.get("image") or {}).get("id")
                else:
                    continue
                out.append({
                    "phone": phone,
                    "text": text,
                    "message_id": msg.get("id"),
                    "image_id": image_id,
                    "type": mtype,
                })
    return out

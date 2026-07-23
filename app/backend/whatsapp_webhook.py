# -*- coding: utf-8 -*-
"""WhatsApp Webhook: Signatur + Payload-Parsing mit Tenant-Metadaten."""
from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any


def app_secret() -> str:
    return (os.getenv("META_APP_SECRET") or os.getenv("FACEBOOK_APP_SECRET") or "").strip()


def verify_signature(payload: bytes, signature_header: str | None) -> bool:
    """Meta X-Hub-Signature-256. Ohne App-Secret: nur loggen, nicht blockieren (Migration)."""
    secret = app_secret()
    if not secret:
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature_header[7:], expected)


def parse_incoming_messages(payload: dict) -> list[dict[str, Any]]:
    """Wie jarvis_bot.parse_whatsapp_payload, plus phone_number_id / waba_id."""
    out: list[dict[str, Any]] = []
    for entry in payload.get("entry") or []:
        waba_id = (entry.get("id") or "").strip()
        for change in entry.get("changes") or []:
            val = change.get("value") or {}
            meta = val.get("metadata") or {}
            phone_number_id = (meta.get("phone_number_id") or "").strip()
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
                    "phone_number_id": phone_number_id,
                    "waba_id": waba_id,
                })
    return out

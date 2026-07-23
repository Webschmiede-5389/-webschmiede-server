# -*- coding: utf-8 -*-
"""Meta Embedded Signup: OAuth-Code → Token → kunden/*.json."""
from __future__ import annotations

import os
from typing import Any

import requests

from whatsapp_tenant import GRAPH, save_whatsapp_to_kunde, subscribe_waba_webhooks

META_APP_ID = (os.getenv("META_APP_ID") or os.getenv("FACEBOOK_APP_ID") or "").strip()
META_APP_SECRET = (os.getenv("META_APP_SECRET") or os.getenv("FACEBOOK_APP_SECRET") or "").strip()
META_EMBEDDED_CONFIG_ID = (os.getenv("META_EMBEDDED_CONFIG_ID") or "").strip()
PUBLIC_BASE_URL = (os.getenv("PUBLIC_BASE_URL") or "https://digitalehandwerkskunst.de").rstrip("/")


def embedded_config(kunde_id: str) -> dict[str, Any]:
    configured = bool(META_APP_ID and META_APP_SECRET)
    return {
        "ok": configured,
        "kunde_id": kunde_id.upper(),
        "app_id": META_APP_ID if configured else "",
        "embedded_config_id": META_EMBEDDED_CONFIG_ID,
        "redirect_uri": f"{PUBLIC_BASE_URL}/onboarding?k={kunde_id.upper()}",
        "webhook_url": f"{PUBLIC_BASE_URL}/api/whatsapp/webhook",
        "hint": (
            "Meta Embedded Signup: Button verbindet WhatsApp Business des Kunden. "
            "META_APP_ID + META_APP_SECRET in Agency Setup nötig."
            if configured
            else "META_APP_ID und META_APP_SECRET fehlen noch (Agency Setup)."
        ),
    }


def exchange_code(code: str) -> dict[str, Any]:
    if not META_APP_ID or not META_APP_SECRET:
        return {"ok": False, "error": "META_APP_ID oder META_APP_SECRET fehlt"}
    code = (code or "").strip()
    if not code:
        return {"ok": False, "error": "OAuth-Code fehlt"}
    try:
        r = requests.get(
            f"{GRAPH}/oauth/access_token",
            params={
                "client_id": META_APP_ID,
                "client_secret": META_APP_SECRET,
                "code": code,
            },
            timeout=25,
        )
        data = r.json() if r.content else {}
        token = (data.get("access_token") or "").strip()
        if not token:
            err = (data.get("error") or {}).get("message") or r.text[:200]
            return {"ok": False, "error": f"Token-Tausch fehlgeschlagen: {err}"}
        return {"ok": True, "access_token": token}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}


def fetch_phone_display(phone_number_id: str, access_token: str) -> str:
    try:
        r = requests.get(
            f"{GRAPH}/{phone_number_id}",
            params={"fields": "display_phone_number"},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        data = r.json() if r.content else {}
        return (data.get("display_phone_number") or "").strip()
    except Exception:
        return ""


def complete_embedded_signup(
    kunde_id: str,
    *,
    code: str,
    phone_number_id: str,
    waba_id: str = "",
) -> dict[str, Any]:
    """Nach Meta Embedded Signup: Code tauschen, Kunde speichern, WABA subscriben."""
    phone_number_id = (phone_number_id or "").strip()
    waba_id = (waba_id or "").strip()
    if not phone_number_id:
        return {"ok": False, "error": "phone_number_id fehlt"}

    exchanged = exchange_code(code)
    if not exchanged.get("ok"):
        return exchanged
    token = exchanged["access_token"]

    display = fetch_phone_display(phone_number_id, token)
    saved = save_whatsapp_to_kunde(
        kunde_id,
        phone_number_id=phone_number_id,
        waba_id=waba_id,
        business_phone=display,
        access_token=token,
        enabled=True,
    )
    if not saved.get("ok"):
        return saved

    sub = subscribe_waba_webhooks(waba_id, token) if waba_id else {"ok": True, "skipped": True}
    return {
        "ok": True,
        "kunde_id": kunde_id.upper(),
        "phone_number_id": phone_number_id,
        "waba_id": waba_id,
        "business_phone": display,
        "webhook_subscription": sub,
        "message": "WhatsApp verbunden und gespeichert.",
    }

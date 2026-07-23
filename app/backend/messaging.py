# -*- coding: utf-8 -*-
"""Messaging-Basis (GHL-Ersatz): SMS via seven.io + WhatsApp via Meta Cloud API.

Pro Kunde: Nummern in Env / kunden.json.
Agentur-Standard: gleicher Stack, kein GoHighLevel.
"""
from __future__ import annotations

import os
import re
from typing import Any

import requests

GRAPH = "https://graph.facebook.com/v21.0"
SEVEN_SMS = "https://gateway.seven.io/api/sms"


def normalize_phone(raw: str) -> str:
    s = re.sub(r"[^\d+]", "", (raw or "").strip())
    if s.startswith("00"):
        s = "+" + s[2:]
    if s.startswith("0") and not s.startswith("+"):
        s = "+49" + s[1:]
    if s and not s.startswith("+") and s.isdigit():
        s = "+" + s
    return s


def digits_only(phone: str) -> str:
    return re.sub(r"\D", "", normalize_phone(phone))


def sms_config() -> dict[str, Any]:
    enabled = os.getenv("SMS_ENABLED", "").lower() in ("1", "true", "yes")
    key = (os.getenv("SMS_API_KEY") or "").strip()
    return {
        "enabled": enabled,
        "configured": bool(key),
        "sender": (os.getenv("SMS_SENDER") or "Webschmiede").strip()[:11],
        "owner_phone": normalize_phone(os.getenv("OWNER_PHONE") or ""),
    }


def whatsapp_config() -> dict[str, Any]:
    token = (os.getenv("WHATSAPP_ACCESS_TOKEN") or "").strip()
    phone_id = (os.getenv("WHATSAPP_PHONE_NUMBER_ID") or "").strip()
    verify = (os.getenv("WHATSAPP_VERIFY_TOKEN") or "").strip()
    waba = (os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID") or "").strip()
    display = (os.getenv("WHATSAPP_DISPLAY_PHONE") or "").strip()
    return {
        "enabled": bool(token and phone_id),
        "configured": bool(token and phone_id),
        "phone_number_id": phone_id,
        "business_account_id": waba,
        "display_phone": display,
        "verify_token_set": bool(verify),
        "webhook_path": "/api/whatsapp/webhook",
    }


def tenant_status() -> dict[str, Any]:
    from whatsapp_tenant import all_configured_tenants

    tenants = all_configured_tenants()
    return {
        "multi_tenant": True,
        "tenant_count": len(tenants),
        "tenants": [
            {
                "kunde_id": t.get("kunde_id") or "agency",
                "name": t.get("name", ""),
                "phone_number_id": t.get("phone_number_id", ""),
                "role": t.get("role", ""),
            }
            for t in tenants
        ],
    }


def status() -> dict[str, Any]:
    sms = sms_config()
    wa = whatsapp_config()
    base = {
        "ok": sms["configured"] or wa["configured"],
        "sms": sms,
        "whatsapp": wa,
        "recommendation": (
            "Meta WhatsApp Cloud API (multi-tenant) + SMS-Gateway. "
            "GHL nicht nötig. Embedded Signup pro Kunde."
        ),
        "setup_steps": [
            "META_APP_ID + META_APP_SECRET in Agency Setup",
            "Agentur: WhatsApp Token + Phone Number ID",
            "Kunden: Onboarding → WhatsApp verbinden (Embedded Signup)",
            "Webhook: https://digitalehandwerkskunst.de/api/whatsapp/webhook",
        ],
    }
    try:
        base["whatsapp_tenants"] = tenant_status()
    except Exception:
        pass
    return base


def send_sms(
    to: str,
    text: str,
    *,
    api_key: str | None = None,
    sender: str | None = None,
) -> dict[str, Any]:
    to_n = normalize_phone(to)
    key = (api_key or os.getenv("SMS_API_KEY") or "").strip()
    from_id = (sender or os.getenv("SMS_SENDER") or "Webschmiede").strip()[:11]
    if not to_n:
        return {"ok": False, "error": "Telefonnummer fehlt", "channel": "sms"}
    if not key:
        return {"ok": False, "error": "SMS_API_KEY fehlt", "channel": "sms"}
    try:
        r = requests.post(
            SEVEN_SMS,
            headers={"X-Api-Key": key},
            data={"to": to_n, "text": (text or "")[:1600], "from": from_id},
            timeout=15,
        )
        if r.status_code in (200, 201):
            return {"ok": True, "channel": "sms", "to": to_n, "message": "SMS gesendet"}
        return {
            "ok": False,
            "channel": "sms",
            "to": to_n,
            "error": f"seven.io HTTP {r.status_code}: {r.text[:160]}",
        }
    except Exception as exc:
        return {"ok": False, "channel": "sms", "to": to_n, "error": str(exc)[:160]}


def send_whatsapp_text(
    to: str,
    body: str,
    *,
    access_token: str | None = None,
    phone_number_id: str | None = None,
) -> dict[str, Any]:
    """Freitext nur innerhalb 24h-Fenster (Kunde hat geschrieben) oder nach Opt-in-Session."""
    to_d = digits_only(to)
    token = (access_token or os.getenv("WHATSAPP_ACCESS_TOKEN") or "").strip()
    phone_id = (phone_number_id or os.getenv("WHATSAPP_PHONE_NUMBER_ID") or "").strip()
    if not to_d:
        return {"ok": False, "error": "Telefonnummer fehlt", "channel": "whatsapp"}
    if not token or not phone_id:
        return {
            "ok": False,
            "error": "WHATSAPP_ACCESS_TOKEN oder PHONE_NUMBER_ID fehlt",
            "channel": "whatsapp",
        }
    try:
        r = requests.post(
            f"{GRAPH}/{phone_id}/messages",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "to": to_d,
                "type": "text",
                "text": {"body": (body or "")[:4096]},
            },
            timeout=20,
        )
        data = r.json() if r.content else {}
        if r.status_code in (200, 201) and data.get("messages"):
            mid = (data["messages"][0] or {}).get("id", "")
            return {
                "ok": True,
                "channel": "whatsapp",
                "to": to_d,
                "message_id": mid,
                "message": "WhatsApp gesendet",
            }
        err = (data.get("error") or {}).get("message") or r.text[:160]
        return {
            "ok": False,
            "channel": "whatsapp",
            "to": to_d,
            "error": f"Meta HTTP {r.status_code}: {err}",
        }
    except Exception as exc:
        return {"ok": False, "channel": "whatsapp", "to": to_d, "error": str(exc)[:160]}


def send_whatsapp_template(
    to: str,
    template_name: str,
    *,
    language: str = "de",
    components: list | None = None,
    access_token: str | None = None,
    phone_number_id: str | None = None,
) -> dict[str, Any]:
    """Business-initiated: genehmigte Meta-Template-Nachricht."""
    to_d = digits_only(to)
    token = (access_token or os.getenv("WHATSAPP_ACCESS_TOKEN") or "").strip()
    phone_id = (phone_number_id or os.getenv("WHATSAPP_PHONE_NUMBER_ID") or "").strip()
    name = (template_name or "").strip()
    if not to_d or not name:
        return {"ok": False, "error": "to oder template_name fehlt", "channel": "whatsapp"}
    if not token or not phone_id:
        return {
            "ok": False,
            "error": "WHATSAPP_ACCESS_TOKEN oder PHONE_NUMBER_ID fehlt",
            "channel": "whatsapp",
        }
    payload: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "to": to_d,
        "type": "template",
        "template": {
            "name": name,
            "language": {"code": language or "de"},
        },
    }
    if components:
        payload["template"]["components"] = components
    try:
        r = requests.post(
            f"{GRAPH}/{phone_id}/messages",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )
        data = r.json() if r.content else {}
        if r.status_code in (200, 201) and data.get("messages"):
            mid = (data["messages"][0] or {}).get("id", "")
            return {
                "ok": True,
                "channel": "whatsapp",
                "to": to_d,
                "message_id": mid,
                "template": name,
                "message": f"WhatsApp-Template „{name}“ gesendet",
            }
        err = (data.get("error") or {}).get("message") or r.text[:160]
        return {
            "ok": False,
            "channel": "whatsapp",
            "to": to_d,
            "error": f"Meta HTTP {r.status_code}: {err}",
        }
    except Exception as exc:
        return {"ok": False, "channel": "whatsapp", "to": to_d, "error": str(exc)[:160]}


def send_notify(
    to: str,
    text: str,
    *,
    prefer: str = "auto",
) -> dict[str, Any]:
    """auto: WhatsApp wenn konfiguriert, sonst SMS. prefer=sms|whatsapp|auto."""
    prefer = (prefer or "auto").lower()
    wa = whatsapp_config()
    sms = sms_config()
    if prefer == "whatsapp" or (prefer == "auto" and wa["configured"]):
        result = send_whatsapp_text(to, text)
        if result.get("ok") or prefer == "whatsapp":
            return result
    if sms["configured"] or prefer == "sms":
        return send_sms(to, text)
    return {
        "ok": False,
        "error": "Weder WhatsApp noch SMS konfiguriert",
        "channel": "none",
    }


def test_sms(to: str | None = None) -> dict[str, Any]:
    target = normalize_phone(to or os.getenv("OWNER_PHONE") or "")
    if not target:
        return {"ok": False, "error": "Keine Test-Nummer (OWNER_PHONE oder to)"}
    return send_sms(
        target,
        "Webschmiede Test-SMS: Messaging-Basis OK (seven.io).",
    )


def send_whatsapp_for_kunde(
    kunde_id: str,
    to: str,
    text: str = "",
    *,
    template_name: str = "",
    language: str = "de",
    components: list | None = None,
) -> dict[str, Any]:
    from whatsapp_tenant import credentials_for_kunde_id

    creds = credentials_for_kunde_id(kunde_id)
    if not creds:
        return {"ok": False, "error": f"WhatsApp für {kunde_id or 'Agentur'} nicht konfiguriert", "channel": "whatsapp"}
    if template_name:
        return send_whatsapp_template(
            to,
            template_name,
            language=language,
            components=components,
            access_token=creds["access_token"],
            phone_number_id=creds["phone_number_id"],
        )
    return send_whatsapp_text(
        to,
        text,
        access_token=creds["access_token"],
        phone_number_id=creds["phone_number_id"],
    )


def test_whatsapp(to: str | None = None) -> dict[str, Any]:
    target = normalize_phone(to or os.getenv("OWNER_PHONE") or "")
    if not target:
        return {"ok": False, "error": "Keine Test-Nummer (OWNER_PHONE oder to)"}
    # Freitext: nur wenn Empfänger in 24h geschrieben hat — sonst Fehler von Meta erklären
    result = send_whatsapp_text(
        target,
        "Webschmiede Test: WhatsApp Cloud API OK.",
    )
    if not result.get("ok") and "template" in (result.get("error") or "").lower():
        result["hint"] = (
            "Außerhalb des 24h-Fensters brauchst du ein genehmigtes Template "
            "(Meta Business → WhatsApp → Vorlagen)."
        )
    elif not result.get("ok"):
        result["hint"] = (
            "Wenn Meta „undeliverable“ / Fenster meldet: erst von diesem Handy "
            "an die Business-Nummer schreiben, oder Template nutzen."
        )
    return result


def verify_meta_phone() -> dict[str, Any]:
    """Phone Number ID gegen Graph API prüfen (ohne Nachricht)."""
    token = (os.getenv("WHATSAPP_ACCESS_TOKEN") or "").strip()
    phone_id = (os.getenv("WHATSAPP_PHONE_NUMBER_ID") or "").strip()
    if not token or not phone_id:
        return {"ok": False, "error": "Token oder Phone Number ID fehlt"}
    try:
        r = requests.get(
            f"{GRAPH}/{phone_id}",
            params={"fields": "display_phone_number,verified_name,quality_rating"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        data = r.json() if r.content else {}
        if r.status_code == 200 and data.get("id"):
            return {
                "ok": True,
                "message": (
                    f"Meta OK: {data.get('verified_name') or 'WA'} "
                    f"{data.get('display_phone_number') or phone_id}"
                ),
                "display_phone_number": data.get("display_phone_number"),
                "verified_name": data.get("verified_name"),
                "quality_rating": data.get("quality_rating"),
            }
        err = (data.get("error") or {}).get("message") or r.text[:160]
        return {"ok": False, "error": err}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:160]}

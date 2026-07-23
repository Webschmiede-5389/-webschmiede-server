# -*- coding: utf-8 -*-
"""Multi-Tenant WhatsApp: Credentials pro Kunde (kunden/*.json) + Agentur-Fallback."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

GRAPH = "https://graph.facebook.com/v21.0"
KUNDEN_DIR = Path(os.getenv("KUNDEN_DIR", Path(__file__).resolve().parents[1] / "kunden"))
AGENCY_KID = "__agency__"


def _load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def list_kunden_files() -> list[Path]:
    if not KUNDEN_DIR.is_dir():
        return []
    return sorted(KUNDEN_DIR.glob("*.json"))


def agency_credentials() -> dict[str, str]:
    return {
        "kunde_id": "",
        "role": "agency",
        "access_token": (os.getenv("WHATSAPP_ACCESS_TOKEN") or "").strip(),
        "phone_number_id": (os.getenv("WHATSAPP_PHONE_NUMBER_ID") or "").strip(),
        "waba_id": (os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID") or "").strip(),
        "display_phone": (os.getenv("WHATSAPP_DISPLAY_PHONE") or "").strip(),
    }


def _token_for_kunde(k: dict, kid: str) -> str:
    wa = k.get("whatsapp") or {}
    direct = (wa.get("access_token") or "").strip()
    if direct:
        return direct
    env_key = (wa.get("access_token_env") or f"WHATSAPP_ACCESS_TOKEN_{kid}").strip()
    return (os.getenv(env_key) or "").strip()


def credentials_from_kunde(k: dict) -> dict[str, Any] | None:
    kid = (k.get("id") or "").upper()
    wa = k.get("whatsapp") or {}
    if not wa.get("enabled", False):
        return None
    phone_id = (wa.get("phone_number_id") or "").strip()
    token = _token_for_kunde(k, kid)
    if not phone_id or not token:
        return None
    return {
        "kunde_id": kid,
        "role": "client",
        "access_token": token,
        "phone_number_id": phone_id,
        "waba_id": (wa.get("waba_id") or "").strip(),
        "display_phone": (wa.get("business_phone") or "").strip(),
        "allowed_phones": wa.get("allowed_phones") or [],
    }


def credentials_for_kunde_id(kunde_id: str) -> dict[str, Any] | None:
    kid = (kunde_id or "").strip().upper()
    if not kid:
        ag = agency_credentials()
        if ag["access_token"] and ag["phone_number_id"]:
            return ag
        return None
    for path in list_kunden_files():
        if not path.name.startswith(kid):
            continue
        k = _load_json(path)
        if k:
            creds = credentials_from_kunde(k)
            if creds:
                return creds
    return None


def resolve_by_phone_number_id(phone_number_id: str) -> dict[str, Any] | None:
    pid = (phone_number_id or "").strip()
    if not pid:
        return None
    ag = agency_credentials()
    if ag["phone_number_id"] == pid and ag["access_token"]:
        return ag
    for path in list_kunden_files():
        k = _load_json(path)
        if not k:
            continue
        wa = k.get("whatsapp") or {}
        if (wa.get("phone_number_id") or "").strip() == pid:
            return credentials_from_kunde(k)
    return None


def all_configured_tenants() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    ag = agency_credentials()
    if ag["access_token"] and ag["phone_number_id"]:
        out.append({**ag, "name": "Digitale Handwerkskunst (Agentur)"})
    for path in list_kunden_files():
        k = _load_json(path)
        if not k:
            continue
        creds = credentials_from_kunde(k)
        if creds:
            out.append({**creds, "name": k.get("name") or creds["kunde_id"]})
    return out


def save_whatsapp_to_kunde(
    kunde_id: str,
    *,
    phone_number_id: str,
    waba_id: str = "",
    business_phone: str = "",
    access_token: str = "",
    enabled: bool = True,
) -> dict[str, Any]:
    from stripe_billing import load_kunde, save_kunde

    loaded = load_kunde(kunde_id)
    if not loaded:
        return {"ok": False, "error": f"Kunde {kunde_id} nicht gefunden"}
    k, path = loaded
    wa = dict(k.get("whatsapp") or {})
    wa["enabled"] = enabled
    wa["phone_number_id"] = (phone_number_id or "").strip()
    wa["waba_id"] = (waba_id or "").strip()
    if business_phone:
        wa["business_phone"] = business_phone.strip()
    if access_token:
        wa["access_token"] = access_token.strip()
    wa["embedded_connected_at"] = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    k["whatsapp"] = wa
    save_kunde(k, path)
    return {"ok": True, "kunde_id": kunde_id.upper(), "whatsapp": wa}


def subscribe_waba_webhooks(waba_id: str, access_token: str) -> dict[str, Any]:
    import requests

    if not waba_id or not access_token:
        return {"ok": False, "error": "waba_id oder token fehlt"}
    try:
        r = requests.post(
            f"{GRAPH}/{waba_id}/subscribed_apps",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
        data = r.json() if r.content else {}
        if r.status_code in (200, 201) and data.get("success") is not False:
            return {"ok": True, "message": "WABA Webhook-Subscription OK"}
        err = (data.get("error") or {}).get("message") or r.text[:160]
        return {"ok": False, "error": err}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:160]}

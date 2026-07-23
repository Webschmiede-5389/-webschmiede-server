"""Lexware Office (ehem. lexoffice) REST API."""
from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

import requests

from integrations import log_integration, resolve_env_secret

log = logging.getLogger(__name__)

BASE_URL = "https://api.lexware.io/v1"


class LexwareError(Exception):
    pass


class LexwareClient:
    def __init__(self, api_key: str, *, timeout: int = 12):
        key = (api_key or "").strip()
        if not key:
            raise LexwareError("Kein Lexware API-Key konfiguriert")
        self.api_key = key
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    def ping(self) -> dict:
        r = self.session.get(f"{BASE_URL}/profile", timeout=self.timeout)
        if r.status_code == 401:
            raise LexwareError("Lexware API-Key ungültig")
        if r.status_code >= 400:
            raise LexwareError(f"Lexware HTTP {r.status_code}: {r.text[:200]}")
        return r.json()

    def find_contact_by_email(self, email: str) -> dict | None:
        em = (email or "").strip().lower()
        if not em:
            return None
        r = self.session.get(
            f"{BASE_URL}/contacts",
            params={"email": em, "size": 1},
            timeout=self.timeout,
        )
        if r.status_code >= 400:
            return None
        data = r.json()
        items = data.get("content") if isinstance(data, dict) else None
        if items:
            return items[0]
        return None

    def create_contact_from_order(self, order: dict) -> dict:
        first = (order.get("first_name") or "").strip() or "Kunde"
        last = (order.get("last_name") or "").strip() or "Portal"
        email = (order.get("email") or "").strip()
        phone = (order.get("phone") or "").strip()
        address = (order.get("address") or "").strip()

        payload: dict[str, Any] = {
            "version": 0,
            "roles": {"customer": {}},
            "person": {"firstName": first, "lastName": last},
            "note": f"Webschmiede Portal · Bestellnr. {order.get('order_number', '')}",
        }

        if email:
            payload["emailAddresses"] = {"private": [email]}
        if phone:
            payload["phoneNumbers"] = {"mobile": [phone]}
        if address:
            payload["addresses"] = {
                "billing": [
                    {
                        "street": address[:100],
                        "city": "",
                        "zip": "",
                        "countryCode": "DE",
                    }
                ]
            }

        r = self.session.post(f"{BASE_URL}/contacts", json=payload, timeout=self.timeout)
        if r.status_code >= 400:
            raise LexwareError(f"Kontakt anlegen fehlgeschlagen ({r.status_code}): {r.text[:300]}")
        return r.json()


def _lexware_cfg(cfg: dict) -> dict:
    return dict(cfg.get("lexware") or {})


def _api_key(kunde: dict | None, cfg: dict) -> str:
    kid = ((kunde or {}).get("id") or "").upper()
    lx = _lexware_cfg(cfg)
    return resolve_env_secret(
        lx.get("api_key_env") or "",
        kid=kid,
        fallback_prefix="LEXWARE_API_KEY",
    )


def lexware_status(kunde: dict | None, cfg: dict) -> dict:
    lx = _lexware_cfg(cfg)
    kid = ((kunde or {}).get("id") or "").upper()
    key = _api_key(kunde, cfg)
    enabled = bool(lx.get("enabled")) and bool(key)
    return {
        "id": "lexware_office",
        "name": "Lexware Office",
        "enabled": enabled,
        "configured": bool(key),
        "sync_contacts": bool(lx.get("sync_contacts", True)),
        "sync_invoices": bool(lx.get("sync_invoices", False)),
        "api_key_env": lx.get("api_key_env") or f"LEXWARE_API_KEY_{kid}",
    }


def _ensure_lexware_contact_column(db: sqlite3.Connection) -> None:
    try:
        db.execute("ALTER TABLE contacts ADD COLUMN lexware_contact_id TEXT")
    except Exception:
        pass


def _get_stored_lexware_id(db: sqlite3.Connection, phone: str) -> str | None:
    row = db.execute(
        "SELECT lexware_contact_id FROM contacts WHERE phone=?",
        (phone,),
    ).fetchone()
    if not row:
        return None
    return (row["lexware_contact_id"] or "").strip() or None


def _store_lexware_id(db: sqlite3.Connection, phone: str, lex_id: str) -> None:
    _ensure_lexware_contact_column(db)
    db.execute(
        "UPDATE contacts SET lexware_contact_id=? WHERE phone=?",
        (lex_id, phone),
    )
    db.commit()


def sync_order_contact(
    db: sqlite3.Connection,
    order: dict,
    *,
    kunde: dict | None,
    cfg: dict,
) -> dict:
    """Bestellkontakt nach Lexware spiegeln (wenn aktiviert)."""
    lx = _lexware_cfg(cfg)
    if not lx.get("enabled"):
        return {"provider": "lexware_office", "skipped": True, "reason": "disabled"}
    if not lx.get("sync_contacts", True):
        return {"provider": "lexware_office", "skipped": True, "reason": "sync_contacts off"}

    phone = (order.get("phone") or "").strip()
    order_no = (order.get("order_number") or "").strip()

    try:
        client = LexwareClient(_api_key(kunde, cfg))
    except LexwareError as exc:
        log_integration(
            db,
            provider="lexware_office",
            action="sync_contact",
            ref=order_no,
            status="error",
            detail=str(exc),
        )
        return {"provider": "lexware_office", "ok": False, "error": str(exc)}

    if phone:
        existing_id = _get_stored_lexware_id(db, phone)
        if existing_id:
            log_integration(
                db,
                provider="lexware_office",
                action="sync_contact",
                ref=order_no,
                status="skipped",
                detail=f"existing {existing_id}",
            )
            return {
                "provider": "lexware_office",
                "ok": True,
                "skipped": True,
                "lexware_contact_id": existing_id,
            }

    email = (order.get("email") or "").strip()
    if email:
        found = client.find_contact_by_email(email)
        if found and found.get("id"):
            lex_id = found["id"]
            if phone:
                _store_lexware_id(db, phone, lex_id)
            log_integration(
                db,
                provider="lexware_office",
                action="sync_contact",
                ref=order_no,
                status="linked",
                detail=lex_id,
            )
            return {
                "provider": "lexware_office",
                "ok": True,
                "linked": True,
                "lexware_contact_id": lex_id,
            }

    try:
        created = client.create_contact_from_order(order)
    except LexwareError as exc:
        log_integration(
            db,
            provider="lexware_office",
            action="sync_contact",
            ref=order_no,
            status="error",
            detail=str(exc),
        )
        return {"provider": "lexware_office", "ok": False, "error": str(exc)}

    lex_id = created.get("id") or ""
    if phone and lex_id:
        _store_lexware_id(db, phone, lex_id)

    log_integration(
        db,
        provider="lexware_office",
        action="sync_contact",
        ref=order_no,
        status="created",
        detail=lex_id,
    )
    return {"provider": "lexware_office", "ok": True, "created": True, "lexware_contact_id": lex_id}


def test_connection(kunde: dict | None, cfg: dict) -> dict:
    try:
        client = LexwareClient(_api_key(kunde, cfg))
        profile = client.ping()
        org = profile.get("companyName") or profile.get("organizationId") or "OK"
        return {"ok": True, "organization": org}
    except LexwareError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

"""Externe Anbindungen pro Kunde (Lexware, sevDesk, …)."""
from __future__ import annotations

import json
import logging
import os
import sqlite3
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

KUNDEN_DIR = Path(os.getenv("KUNDEN_DIR", Path(__file__).resolve().parents[2] / "kunden"))


def load_kunde_json(kid: str) -> dict | None:
    kid = (kid or "").strip().upper()
    if not kid or not KUNDEN_DIR.is_dir():
        return None
    for path in KUNDEN_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if (data.get("id") or "").upper() == kid:
            return data
    return None


def resolve_env_secret(env_name: str, *, kid: str = "", fallback_prefix: str = "") -> str:
    """API-Key aus benanntem Env oder LEXWARE_API_KEY_{KID} / global."""
    name = (env_name or "").strip()
    if name:
        val = os.getenv(name, "").strip()
        if val:
            return val
    if kid and fallback_prefix:
        val = os.getenv(f"{fallback_prefix}_{kid}", "").strip()
        if val:
            return val
        val = os.getenv(fallback_prefix, "").strip()
        if val:
            return val
    return ""


def integrations_config(kunde: dict | None) -> dict:
    if not kunde:
        return {}
    return dict(kunde.get("integrations") or {})


def sync_order(db: sqlite3.Connection, order: dict, *, kid: str) -> list[dict]:
    """Nach neuer Bestellung: aktive Integrationen anstoßen."""
    kunde = load_kunde_json(kid)
    cfg = integrations_config(kunde)
    if not cfg:
        return []

    results: list[dict] = []
    buchhaltung = (cfg.get("buchhaltung") or "").strip().lower()

    if buchhaltung in ("lexware_office", "lexware", "lexoffice"):
        from integrations.lexware import sync_order_contact

        results.append(sync_order_contact(db, order, kunde=kunde, cfg=cfg))

    return results


def integration_status(kid: str) -> dict[str, Any]:
    kunde = load_kunde_json(kid)
    cfg = integrations_config(kunde)
    buchhaltung = (cfg.get("buchhaltung") or "").strip().lower()
    lex_cfg = cfg.get("lexware") or {}

    out: dict[str, Any] = {
        "kunde_id": kid,
        "buchhaltung": buchhaltung or None,
        "providers": [],
    }

    if buchhaltung in ("lexware_office", "lexware", "lexoffice"):
        from integrations.lexware import lexware_status

        out["providers"].append(lexware_status(kunde, cfg))

    return out


def log_integration(
    db: sqlite3.Connection,
    *,
    provider: str,
    action: str,
    ref: str,
    status: str,
    detail: str = "",
) -> None:
    try:
        db.execute(
            """INSERT INTO integration_log (provider, action, ref, status, detail)
               VALUES (?,?,?,?,?)""",
            (provider, action, ref, status, detail[:2000]),
        )
        db.commit()
    except Exception as exc:
        log.warning("integration_log: %s", exc)

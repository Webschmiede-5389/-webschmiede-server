# -*- coding: utf-8 -*-
"""Nils adapter for CRM prospect create (narrow write)."""
from __future__ import annotations

import importlib.util
import os
import sys
from typing import Any

from nils_job_runtime import crm_offer_service as offer_svc

_PROSPECT = None


def _load():
    global _PROSPECT
    if _PROSPECT is not None:
        return _PROSPECT
    path = offer_svc._crm_root() / "app" / "services" / "prospect_create.py"
    if not path.is_file():
        raise FileNotFoundError(f"CRM prospect_create nicht gefunden: {path}")
    spec = importlib.util.spec_from_file_location("crm_prospect_create_svc", path)
    if spec is None or spec.loader is None:
        raise ImportError(str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["crm_prospect_create_svc"] = mod
    spec.loader.exec_module(mod)
    _PROSPECT = mod
    return mod


def write_enabled() -> bool:
    raw = (os.getenv("NILS_CAP_CRM_PROSPECT_CREATE") or "0").strip().lower()
    return raw not in ("0", "false", "no", "off", "")


def find_exact(company_name: str) -> dict[str, Any] | None:
    mod = _load()
    con = offer_svc._connect(readonly=True)
    try:
        return mod.find_company_exact(
            con, tenant_id=offer_svc.tenant_id(), name=company_name
        )
    finally:
        con.close()


def create_prospect(
    *,
    company_name: str,
    contact_name: str = "",
    notes: str = "",
    lead_source: str = "nils_telegram",
) -> Any:
    if not write_enabled():
        raise PermissionError("NILS_CAP_CRM_PROSPECT_CREATE ist aus")
    mod = _load()
    con = offer_svc._connect(readonly=False)
    try:
        return mod.create_prospect(
            con,
            tenant_id=offer_svc.tenant_id(),
            company_name=company_name,
            contact_name=contact_name,
            lead_source=(lead_source or "nils_telegram")[:60],
            notes=notes or "Angelegt via Nils Telegram",
        )
    finally:
        con.close()


def format_created(result: Any) -> str:
    return _load().format_created_telegram(result)


def format_approval(*, company_name: str, contact_name: str = "") -> str:
    return _load().format_approval_prompt(
        company_name=company_name, contact_name=contact_name
    )

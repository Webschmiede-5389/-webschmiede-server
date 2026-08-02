# -*- coding: utf-8 -*-
"""Nils adapter for CRM company/contact/onboarding reads (no writes)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from nils_job_runtime import crm_offer_service as offer_svc


_CUSTOMER_READ = None


def _load_customer_read():
    global _CUSTOMER_READ
    if _CUSTOMER_READ is not None:
        return _CUSTOMER_READ
    path = offer_svc._crm_root() / "app" / "services" / "customer_read.py"
    if not path.is_file():
        raise FileNotFoundError(f"CRM customer_read nicht gefunden: {path}")
    spec = importlib.util.spec_from_file_location("crm_customer_read_svc", path)
    if spec is None or spec.loader is None:
        raise ImportError(str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["crm_customer_read_svc"] = mod
    spec.loader.exec_module(mod)
    _CUSTOMER_READ = mod
    return mod


def probe() -> dict[str, Any]:
    return offer_svc.probe()


def search_companies(query: str) -> list[Any]:
    return offer_svc.search_companies(query)


def get_company_profile(company_id: int) -> Any | None:
    mod = _load_customer_read()
    con = offer_svc._connect(readonly=True)
    try:
        return mod.get_company_profile(
            con, tenant_id=offer_svc.tenant_id(), company_id=company_id
        )
    finally:
        con.close()


def format_profile(profile: Any) -> str:
    return _load_customer_read().format_company_profile_telegram(profile)


def format_company_choices(companies: list[Any]) -> str:
    return offer_svc.format_company_choices(companies)

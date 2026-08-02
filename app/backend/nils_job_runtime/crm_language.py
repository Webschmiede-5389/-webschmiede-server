# -*- coding: utf-8 -*-
"""Nils CRM language helpers — loads CRM lifecycle_policy (same rules as Production)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_POLICY = None


def _crm_root() -> Path:
    from nils_job_runtime import crm_offer_service as crm

    return crm._crm_root()


def policy() -> Any:
    global _POLICY
    if _POLICY is not None:
        return _POLICY
    candidates = [
        Path(__file__).resolve().with_name("crm_lifecycle_policy.py"),
        _crm_root() / "app" / "services" / "lifecycle_policy.py",
    ]
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        raise FileNotFoundError("lifecycle_policy nicht gefunden")
    spec = importlib.util.spec_from_file_location("crm_lifecycle_policy_svc", path)
    if spec is None or spec.loader is None:
        raise ImportError(str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["crm_lifecycle_policy_svc"] = mod
    spec.loader.exec_module(mod)
    _POLICY = mod
    return mod


def ask_company_prompt() -> str:
    return policy().nils_ask_company_prompt()


def company_not_found(query: str) -> str:
    return policy().nils_company_not_found(query)


def offer_company_line(*, company_name: str, lifecycle_status: str | None = None) -> str:
    return policy().nils_offer_company_line(
        company_name=company_name, lifecycle_status=lifecycle_status
    )

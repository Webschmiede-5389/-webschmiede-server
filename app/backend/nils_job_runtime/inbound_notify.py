# -*- coding: utf-8 -*-
"""Sofort-Telegram bei Agency-Inbound (Meta / E-Mail) — Zug D.

Tenant-Isolation: nur Agency-Sales-Tenants, nie Kunden-Delivery (z. B. POL001).
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

log = logging.getLogger("nils_job_runtime.inbound_notify")

_DEFAULT_ALLOW = frozenset(
    {
        "agency",
        "webschmiede",
        "digitalehandwerkskunst",
        "dhk",
        "default",
    }
)
_DEFAULT_DENY = frozenset(
    {
        "pol001",
        "snackhouse",
        "snack-house",
        "customer",
    }
)


def _truthy(name: str, default: str = "0") -> bool:
    return (os.getenv(name) or default).strip().lower() in ("1", "true", "yes", "on")


def enabled() -> bool:
    return _truthy("NILS_INBOUND_TELEGRAM", "1")


def meta_tenant_allowed(tenant_id: str) -> bool:
    tid = (tenant_id or "").strip().lower()
    deny_raw = (os.getenv("NILS_INBOUND_META_DENY") or "").strip()
    deny = {x.strip().lower() for x in deny_raw.split(",") if x.strip()} or set(
        _DEFAULT_DENY
    )
    if tid in deny or any(tid.startswith(d) for d in deny):
        return False
    allow_raw = (os.getenv("NILS_INBOUND_META_TENANTS") or "").strip()
    if allow_raw in ("*", "all"):
        return True
    allow = {x.strip().lower() for x in allow_raw.split(",") if x.strip()} or set(
        _DEFAULT_ALLOW
    )
    if not tid:
        return True  # unkonfiguriert → Agency-Default
    return tid in allow


def score_lead(
    *,
    name: str = "",
    email: str = "",
    phone: str = "",
    company: str = "",
    intent: str = "",
) -> int:
    score = 0
    if (email or "").strip():
        score += 30
    if (phone or "").strip():
        score += 30
    if (name or "").strip():
        score += 15
    if (company or "").strip():
        score += 15
    intent_l = (intent or "").lower()
    if any(
        k in intent_l
        for k in ("website", "webseite", "termin", "angebot", "crm", "bestell")
    ):
        score += 10
    return min(100, score)


def _intent_from_custom(custom: Any) -> str:
    if isinstance(custom, str):
        try:
            custom = json.loads(custom)
        except Exception:
            return custom[:120]
    if not isinstance(custom, dict):
        return ""
    for key in (
        "intent",
        "interesse",
        "interest",
        "anliegen",
        "message",
        "nachricht",
        "company_name",
        "firma",
    ):
        for k, v in custom.items():
            if str(k).lower() == key and str(v).strip():
                return str(v).strip()[:120]
    # first non-empty custom value
    for v in custom.values():
        if str(v).strip():
            return str(v).strip()[:120]
    return ""


def format_inbound_telegram(
    *,
    source: str,
    lead_ref: str,
    name: str = "",
    email: str = "",
    phone: str = "",
    company: str = "",
    intent: str = "",
    subject: str = "",
    is_test: bool = False,
) -> str:
    company_or_name = (company or name or "—").strip()
    intent_txt = (intent or subject or "—").strip()
    sc = score_lead(
        name=name, email=email, phone=phone, company=company, intent=intent_txt
    )
    test = " [TEST]" if is_test else ""
    lines = [
        f"Neuer Inbound-Lead ({source}){test}",
        f"Ref: {lead_ref}",
        f"Firma/Name: {company_or_name}",
        f"Kontakt: {name or '—'}",
        f"Intent: {intent_txt[:140]}",
        f"Score: {sc}/100",
        f"Mail: {email or '—'}",
        f"Tel: {phone or '—'}",
        "",
        f'Annehmen: „Annehmen {lead_ref}“',
        "Liste: „Inbound“ / „Neue Leads“",
        "",
        "Danach Close:",
        f"Feld-Close bei {company_or_name}",
        "notiz: ",
        "nächster Schritt: ",
    ]
    return "\n".join(lines)


def push_owner_telegram(text: str) -> dict[str, Any]:
    if not enabled():
        return {"ok": True, "skipped": "NILS_INBOUND_TELEGRAM aus"}
    try:
        from nils_job_runtime import notify
        import telegram_ops as tg

        owners = tg.owner_chat_ids()
        if not owners:
            return {"ok": False, "error": "kein owner chat"}
        results = [notify._send(str(c), text[:3800]) for c in owners]
        return {"ok": all(r.get("ok") for r in results), "n": len(results)}
    except Exception as e:
        log.exception("inbound_telegram_push")
        return {"ok": False, "error": str(e)[:160]}


def notify_meta_lead(lead: dict[str, Any], *, tenant_id: str) -> dict[str, Any]:
    if not enabled():
        return {"ok": True, "skipped": "disabled"}
    if not meta_tenant_allowed(tenant_id):
        return {"ok": True, "skipped": "tenant_denied", "tenant": tenant_id}
    custom = lead.get("custom_fields") or {}
    intent = _intent_from_custom(custom)
    company = ""
    if isinstance(custom, dict):
        company = str(
            custom.get("company_name")
            or custom.get("firma")
            or custom.get("company")
            or ""
        ).strip()
    elif isinstance(custom, str):
        try:
            d = json.loads(custom)
            company = str(
                d.get("company_name") or d.get("firma") or d.get("company") or ""
            ).strip()
            intent = intent or _intent_from_custom(d)
        except Exception:
            pass
    lid = lead.get("id") or lead.get("meta_lead_id")
    ref = f"meta:{lid}"
    text = format_inbound_telegram(
        source="Meta",
        lead_ref=ref,
        name=str(lead.get("full_name") or ""),
        email=str(lead.get("email") or ""),
        phone=str(lead.get("phone") or ""),
        company=company,
        intent=intent or str(lead.get("ad_name") or ""),
        is_test=bool(lead.get("is_test")),
    )
    return push_owner_telegram(text)


def notify_agency_email_lead(lead: dict[str, Any]) -> dict[str, Any]:
    if not enabled():
        return {"ok": True, "skipped": "disabled"}
    lid = lead.get("id")
    ref = f"email:{lid}"
    text = format_inbound_telegram(
        source="E-Mail",
        lead_ref=ref,
        name=str(lead.get("name") or ""),
        email=str(lead.get("email") or ""),
        phone=str(lead.get("phone") or ""),
        company=str(lead.get("company") or ""),
        intent=str(lead.get("subject") or ""),
        subject=str(lead.get("subject") or ""),
    )
    return push_owner_telegram(text)


def parse_lead_ref(text: str) -> tuple[str, int] | None:
    """Parse meta:12 / email:5 / #meta-12."""
    t = (text or "").strip()
    m = re.search(r"(?i)\b(meta|email|mail|agency)\s*[:#\-]?\s*(\d+)\b", t)
    if m:
        kind = m.group(1).lower()
        if kind in ("mail", "agency"):
            kind = "email"
        return kind, int(m.group(2))
    m = re.search(r"(?i)#(meta|email)\-?(\d+)\b", t)
    if m:
        return m.group(1).lower(), int(m.group(2))
    return None

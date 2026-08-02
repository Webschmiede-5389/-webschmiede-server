# -*- coding: utf-8 -*-
"""Nils adapter for Second-Manager sales field (pipeline/thread/notes/stage/offer/close)."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

from nils_job_runtime import crm_offer_service as offer_svc

_SALES = None

SM1_CAPS = frozenset(
    {
        "crm.pipeline_read",
        "crm.lead_thread",
        "crm.note_create",
        "crm.deal_stage_update",
        "crm.deal_open",
        "crm.offer_write",
        "crm.deal_close",
    }
)


def _truthy(name: str, default: str = "0") -> bool:
    return (os.getenv(name) or default).strip().lower() in ("1", "true", "yes", "on")


def _load():
    global _SALES
    if _SALES is not None:
        return _SALES
    path = offer_svc._crm_root() / "app" / "services" / "sales_field.py"
    if not path.is_file():
        raise FileNotFoundError(f"sales_field nicht gefunden: {path}")
    spec = importlib.util.spec_from_file_location("crm_sales_field_svc", path)
    if spec is None or spec.loader is None:
        raise ImportError(str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["crm_sales_field_svc"] = mod
    spec.loader.exec_module(mod)
    _SALES = mod
    return mod


def probe() -> dict[str, Any]:
    return offer_svc.probe()


def tenant_id() -> int:
    return offer_svc.tenant_id()


def cap_enabled(capability: str) -> bool:
    """Master SM-1 flag or per-cap. Mandate GO enables via NILS_CAP_CRM_SALES_FIELD."""
    if capability not in SM1_CAPS:
        return False
    if _truthy("NILS_CAP_CRM_SALES_FIELD", "0"):
        return True
    mapping = {
        "crm.pipeline_read": "NILS_CAP_CRM_PIPELINE",
        "crm.lead_thread": "NILS_CAP_CRM_ACTIVITY",
        "crm.note_create": "NILS_CAP_CRM_ACTIVITY",
        "crm.deal_stage_update": "NILS_CAP_CRM_DEAL_WRITE",
        "crm.deal_open": "NILS_CAP_CRM_DEAL_WRITE",
        "crm.offer_write": "NILS_CAP_CRM_OFFER_WRITE",
        "crm.deal_close": "NILS_CAP_CRM_WON_LOST",
    }
    return _truthy(mapping.get(capability, ""), "0")


def search_companies(query: str) -> list[Any]:
    return offer_svc.search_companies(query)


def format_company_choices(companies: list[Any]) -> str:
    return offer_svc.format_company_choices(companies)


def pipeline_board() -> Any:
    mod = _load()
    con = offer_svc._connect(readonly=True)
    try:
        return mod.list_pipeline(con, tenant_id=tenant_id())
    finally:
        con.close()


def format_pipeline(board: Any) -> str:
    return _load().format_pipeline_telegram(board)


def field_briefing() -> str:
    mod = _load()
    con = offer_svc._connect(readonly=True)
    try:
        tid = tenant_id()
        board = mod.list_pipeline(con, tenant_id=tid)
        due = mod.list_due_today(con, tenant_id=tid)
        stale = mod.list_stale_deals(con, tenant_id=tid, quiet_days=3)
        return mod.format_field_briefing(board=board, due=due, stale=stale)
    finally:
        con.close()


def stale_leads_text(*, quiet_days: int = 3) -> str:
    mod = _load()
    con = offer_svc._connect(readonly=True)
    try:
        stale = mod.list_stale_deals(
            con, tenant_id=tenant_id(), quiet_days=quiet_days
        )
        return mod.format_stale_leads_telegram(stale, limit=6)
    finally:
        con.close()


def _sla_hours() -> tuple[float, float, float]:
    def _f(name: str, default: float) -> float:
        try:
            return float(os.getenv(name, str(default)) or default)
        except Exception:
            return default

    return (
        _f("NILS_SLA_HOT_HOURS", 2.0),
        _f("NILS_SLA_WARM_HOURS", 24.0),
        _f("NILS_SLA_SILENT_HOURS", 72.0),
    )


def sla_report_text() -> str:
    mod = _load()
    hot_h, warm_h, silent_h = _sla_hours()
    con = offer_svc._connect(readonly=True)
    try:
        report = mod.build_sla_report(
            con,
            tenant_id=tenant_id(),
            hot_hours=hot_h,
            warm_hours=warm_h,
            silent_hours=silent_h,
        )
        return mod.format_sla_report(report)
    finally:
        con.close()


def evening_debrief_text() -> str:
    mod = _load()
    hot_h, warm_h, silent_h = _sla_hours()
    con = offer_svc._connect(readonly=True)
    try:
        tid = tenant_id()
        report = mod.build_sla_report(
            con,
            tenant_id=tid,
            hot_hours=hot_h,
            warm_hours=warm_h,
            silent_hours=silent_h,
        )
        wins = mod.list_wins_today(con, tenant_id=tid)
        # due today doubles as "tomorrow focus" when next_step_due is set
        due = mod.list_due_today(con, tenant_id=tid, limit=8)
        return mod.format_evening_debrief(
            report=report, wins=wins, due_tomorrow=due
        )
    finally:
        con.close()


def followup_suggestion_text(company_id: int) -> str:
    mod = _load()
    con = offer_svc._connect(readonly=True)
    try:
        return mod.followup_suggestion_for_company(
            con, tenant_id=tenant_id(), company_id=company_id
        )
    finally:
        con.close()


def morning_briefing_text() -> str:
    from nils_job_runtime import manager_briefing as mb

    return mb.morning_briefing_text()


def funnel_review_text(*, days: int = 7) -> str:
    from nils_job_runtime import manager_briefing as mb

    return mb.funnel_review_text(days=days)


def lead_thread(company_id: int) -> Any:
    mod = _load()
    con = offer_svc._connect(readonly=True)
    try:
        return mod.get_lead_thread(con, tenant_id=tenant_id(), company_id=company_id)
    finally:
        con.close()


def format_thread(thread: Any) -> str:
    return _load().format_lead_thread_telegram(thread)


def add_note(
    *,
    company_id: int,
    note: str,
    next_action: str = "",
    deal_id: int | None = None,
) -> dict[str, Any]:
    mod = _load()
    con = offer_svc._connect(readonly=False)
    try:
        return mod.add_note(
            con,
            tenant_id=tenant_id(),
            company_id=company_id,
            note=note,
            next_action=next_action,
            deal_id=deal_id,
        )
    finally:
        con.close()


def update_stage(
    *, company_id: int, stage_query: str, deal_id: int | None = None
) -> dict[str, Any]:
    mod = _load()
    con = offer_svc._connect(readonly=False)
    try:
        return mod.update_deal_stage(
            con,
            tenant_id=tenant_id(),
            company_id=company_id,
            stage_query=stage_query,
            deal_id=deal_id,
        )
    finally:
        con.close()


def ensure_open_deal(
    *, company_id: int, title: str = ""
) -> dict[str, Any]:
    """Offenen Deal bestätigen oder neu anlegen (nach Lost / ohne Deal)."""
    mod = _load()
    con = offer_svc._connect(readonly=False)
    try:
        before = mod.open_deal_for_company(
            con, tenant_id=tenant_id(), company_id=company_id
        )
        deal = mod.ensure_deal_for_company(
            con,
            tenant_id=tenant_id(),
            company_id=company_id,
            title=title,
        )
        return {
            "created": before is None,
            "deal_id": int(deal.get("id") or 0),
            "deal_title": str(deal.get("title") or ""),
            "stage": str(deal.get("stage_name") or ""),
            "company_id": company_id,
        }
    finally:
        con.close()


def resolve_offer_variant(text: str) -> dict[str, Any] | None:
    mod = _load()
    fn = getattr(mod, "resolve_offer_variant", None)
    if not callable(fn):
        return None
    return fn(text or "")


def create_offer(
    *,
    company_id: int,
    title: str = "",
    setup_eur: float | None = None,
    monthly_eur: float | None = None,
    services: str = "",
) -> dict[str, Any]:
    mod = _load()
    con = offer_svc._connect(readonly=False)
    try:
        return mod.create_offer_draft(
            con,
            tenant_id=tenant_id(),
            company_id=company_id,
            title=title,
            setup_eur=setup_eur,
            monthly_eur=monthly_eur,
            services=services,
        )
    finally:
        con.close()


def close_deal(
    *,
    company_id: int,
    outcome: str,
    lost_reason: str = "",
    deal_id: int | None = None,
) -> dict[str, Any]:
    mod = _load()
    con = offer_svc._connect(readonly=False)
    try:
        return mod.close_deal(
            con,
            tenant_id=tenant_id(),
            company_id=company_id,
            outcome=outcome,
            lost_reason=lost_reason,
            deal_id=deal_id,
        )
    finally:
        con.close()

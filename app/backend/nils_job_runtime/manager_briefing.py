# -*- coding: utf-8 -*-
"""Zug E — Morgen-Briefing & Funnel-Review (proaktiver Manager)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from nils_job_runtime import crm_offer_service as offer_svc
from nils_job_runtime import crm_sales_field_service as crm
from nils_job_runtime import inbound_service as inbound
from nils_job_runtime import store

log = logging.getLogger("nils_job_runtime.manager_briefing")


def _tz() -> ZoneInfo:
    import os

    return ZoneInfo(os.getenv("NILS_CALENDAR_TZ") or "Europe/Berlin")


def _open_approvals(limit: int = 8) -> list[dict[str, Any]]:
    try:
        store.ensure_schema()
        con = store.connect()
        try:
            rows = con.execute(
                """
                SELECT job_id, capability, approval_required, progress_message,
                       task_summary, created_at
                FROM nils_jobs
                WHERE status = 'WAITING_FOR_APPROVAL'
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows or []]
        finally:
            con.close()
    except Exception:
        log.exception("open_approvals")
        return []


def _calendar_today_lines(limit: int = 6) -> list[str]:
    try:
        from nils_job_runtime.calendar_connector import CalendarConfig, CalendarConnector

        cfg = CalendarConfig.from_env()
        if not cfg.enabled or cfg.token_status not in ("mock", "valid"):
            return ["Termine: Kalender nicht aktiv"]
        tz = _tz()
        now = datetime.now(tz)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        conn = CalendarConnector(cfg)
        listed = conn.list_events(
            time_min=start.isoformat(),
            time_max=end.isoformat(),
            limit=limit,
        )
        events = listed.get("events") or []
        if not events:
            return ["Termine heute: (keine im Zielkalender)"]
        lines = [f"Termine heute ({cfg.target_name or 'webschmiede'}):"]
        for e in events[:limit]:
            start_s = str(e.get("start_iso") or e.get("start") or "?")[:16]
            lines.append(f"  · {start_s} — {e.get('summary') or '–'}")
        return lines
    except Exception as e:
        log.exception("calendar_today")
        return [f"Termine: nicht lesbar ({type(e).__name__})"]


def morning_briefing_text() -> str:
    """07:30-Lage: Termine · SLA · Inbound · offene Freigaben · Top-Handlungen."""
    lines = ["Morgen-Briefing", ""]
    lines.extend(_calendar_today_lines())
    lines.append("")

    try:
        sla = crm.sla_report_text()
        # compact: first block only
        lines.append("--- SLA ---")
        for ln in sla.splitlines()[:14]:
            lines.append(ln)
    except Exception as e:
        lines.append(f"SLA: Fehler ({type(e).__name__})")

    lines.append("")
    try:
        pending = inbound.list_pending(limit=5)
        lines.append(f"Inbound offen: {len(pending)}")
        for L in pending[:3]:
            who = L.get("company") or L.get("name") or "—"
            lines.append(
                f"  · {L.get('ref')} Score {L.get('score')}/100 — {who}"
            )
        if pending:
            lines.append(f"  → Annehmen {pending[0].get('ref')}")
    except Exception:
        lines.append("Inbound: n/a")

    lines.append("")
    approvals = _open_approvals()
    lines.append(f"Offene Freigaben: {len(approvals)}")
    for a in approvals[:4]:
        cap = a.get("capability") or a.get("approval_required") or "?"
        lines.append(f"  · {a.get('job_id')}: {cap}")

    lines.append("")
    lines.append("Heute Top-Handlungen:")
    actions: list[str] = []
    close_block = ""
    try:
        mod = crm._load()
        con = offer_svc._connect(readonly=True)
        try:
            tid = crm.tenant_id()
            hot_h, warm_h, silent_h = crm._sla_hours()
            report = mod.build_sla_report(
                con,
                tenant_id=tid,
                hot_hours=hot_h,
                warm_hours=warm_h,
                silent_hours=silent_h,
            )
            priority = report.hot + report.warm + report.silent
            for d in priority[:3]:
                actions.append(
                    f"  {len(actions)+1}. {d.company_name or '–'} — "
                    f"{mod.suggest_followup_line(d)[:65]}"
                )
            if priority:
                close_block = (
                    "Close jetzt (Copy-Paste):\n"
                    + mod.feld_close_snippet(priority[0].company_name or "")
                )
        finally:
            con.close()
    except Exception:
        pass
    if not actions:
        actions = [
            "  1. Pipeline heute / Follow-up SLA",
            "  2. Feld-Close nach Tür",
            "  3. Inbound prüfen",
        ]
    lines.extend(actions[:5])
    if close_block:
        lines.append("")
        lines.append(close_block)
    lines.append("")
    lines.append(
        "Feld: `feldkarte` · `Stille Leads` · `setting` · `story gastro`"
    )
    return "\n".join(lines).strip()


def funnel_review_text(*, days: int = 7) -> str:
    mod = crm._load()
    hot_h, warm_h, silent_h = crm._sla_hours()
    con = offer_svc._connect(readonly=True)
    try:
        tid = crm.tenant_id()
        board = mod.list_pipeline(con, tenant_id=tid)
        wins = mod.list_wins_since(con, tenant_id=tid, days=days)
        report = mod.build_sla_report(
            con,
            tenant_id=tid,
            hot_hours=hot_h,
            warm_hours=warm_h,
            silent_hours=silent_h,
        )
        activity_days = mod.count_activity_days(con, tenant_id=tid, days=days)
        return mod.format_funnel_review(
            board=board,
            wins=wins,
            report=report,
            activity_days=activity_days,
            days=days,
        )
    finally:
        con.close()

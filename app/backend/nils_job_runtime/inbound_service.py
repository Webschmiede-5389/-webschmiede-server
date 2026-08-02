# -*- coding: utf-8 -*-
"""Agency Inbound Leads lesen + Annehmen → CRM Prospect/Deal/Follow-up (Zug D)."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from nils_job_runtime import crm_prospect_service as prospect_svc
from nils_job_runtime import crm_sales_field_service as sales_svc
from nils_job_runtime import inbound_notify as inn


def _truthy(name: str, default: str = "0") -> bool:
    return (os.getenv(name) or default).strip().lower() in ("1", "true", "yes", "on")


def enabled() -> bool:
    if _truthy("NILS_CAP_CRM_INBOUND", "0"):
        return True
    # mit Sales-Field oder Prospect freigeschaltet
    return _truthy("NILS_CAP_CRM_SALES_FIELD", "0") or _truthy(
        "NILS_CAP_CRM_PROSPECT_CREATE", "0"
    )


def orders_db_path() -> Path:
    raw = (os.getenv("ORDERS_DB") or os.getenv("NILS_ORDERS_DB") or "").strip()
    if raw:
        return Path(raw)
    if os.name == "nt":
        return Path(__file__).resolve().parents[1] / "orders.db"
    return Path("/root/app/backend/orders.db")


def _connect() -> sqlite3.Connection:
    p = orders_db_path()
    con = sqlite3.connect(str(p), timeout=30)
    con.row_factory = sqlite3.Row
    return con


def _ensure_meta(con: sqlite3.Connection) -> None:
    try:
        import meta_leads as ml

        ml.ensure_tables(con)
    except Exception:
        pass


def _ensure_agency(con: sqlite3.Connection) -> None:
    try:
        import agency_leads as al

        al.ensure_table(con)
    except Exception:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS agency_leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT,
                name TEXT,
                phone TEXT,
                company TEXT,
                source TEXT DEFAULT 'email',
                status TEXT DEFAULT 'lead',
                subject TEXT,
                body_preview TEXT,
                notes TEXT,
                converted_kunde_id TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        con.commit()


def _row(r: Any) -> dict[str, Any]:
    if r is None:
        return {}
    return dict(r)


def list_pending(*, limit: int = 15) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    con = _connect()
    try:
        _ensure_agency(con)
        _ensure_meta(con)
        try:
            rows = con.execute(
                """
                SELECT id, name, email, phone, company, subject, status, source, created_at
                FROM agency_leads
                WHERE (converted_kunde_id IS NULL OR converted_kunde_id = '')
                  AND COALESCE(status,'lead') IN ('lead','neu','open')
                ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
            for r in rows or []:
                d = _row(r)
                intent = str(d.get("subject") or "")
                sc = inn.score_lead(
                    name=str(d.get("name") or ""),
                    email=str(d.get("email") or ""),
                    phone=str(d.get("phone") or ""),
                    company=str(d.get("company") or ""),
                    intent=intent,
                )
                out.append(
                    {
                        "ref": f"email:{d['id']}",
                        "kind": "email",
                        "id": int(d["id"]),
                        "name": d.get("name") or "",
                        "email": d.get("email") or "",
                        "phone": d.get("phone") or "",
                        "company": d.get("company") or "",
                        "intent": intent,
                        "score": sc,
                        "source": "E-Mail",
                    }
                )
        except Exception:
            pass
        try:
            rows = con.execute(
                """
                SELECT id, meta_lead_id, full_name, email, phone, custom_fields,
                       ad_name, status, tenant_id, is_test, created_at
                FROM meta_leads
                WHERE COALESCE(status,'neu') IN ('neu','kontaktiert')
                ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
            for r in rows or []:
                d = _row(r)
                if not inn.meta_tenant_allowed(str(d.get("tenant_id") or "")):
                    continue
                custom = d.get("custom_fields") or {}
                if isinstance(custom, str):
                    try:
                        custom = json.loads(custom)
                    except Exception:
                        custom = {}
                company = ""
                intent = ""
                if isinstance(custom, dict):
                    company = str(
                        custom.get("company_name")
                        or custom.get("firma")
                        or custom.get("company")
                        or ""
                    )
                    intent = inn._intent_from_custom(custom)
                intent = intent or str(d.get("ad_name") or "")
                sc = inn.score_lead(
                    name=str(d.get("full_name") or ""),
                    email=str(d.get("email") or ""),
                    phone=str(d.get("phone") or ""),
                    company=company,
                    intent=intent,
                )
                out.append(
                    {
                        "ref": f"meta:{d['id']}",
                        "kind": "meta",
                        "id": int(d["id"]),
                        "meta_lead_id": d.get("meta_lead_id"),
                        "name": d.get("full_name") or "",
                        "email": d.get("email") or "",
                        "phone": d.get("phone") or "",
                        "company": company,
                        "intent": intent,
                        "score": sc,
                        "source": "Meta",
                        "is_test": bool(d.get("is_test")),
                    }
                )
        except Exception:
            pass
    finally:
        con.close()
    out.sort(key=lambda x: (-int(x.get("score") or 0), -int(x.get("id") or 0)))
    return out[:limit]


def format_list(leads: list[dict[str, Any]]) -> str:
    if not leads:
        return (
            "Inbound: keine offenen Agency-Leads.\n"
            "Wenn Meta/E-Mail eingeht, pusht Nils sofort (Agency-Tenant)."
        )
    lines = [f"Inbound — {len(leads)} offen (Agency-Sales):", ""]
    for L in leads[:12]:
        who = L.get("company") or L.get("name") or "—"
        lines.append(
            f"· {L.get('ref')} [{L.get('source')}] Score {L.get('score')}/100 — {who}"
        )
        if L.get("intent"):
            lines.append(f"  Intent: {str(L['intent'])[:80]}")
        lines.append(f"  → Annehmen {L.get('ref')}")
    lines.append("")
    lines.append("Annehmen → Prospect + Follow-up (mit „ja“), danach Close-Vorlage.")
    top = leads[0]
    who = str(top.get("company") or top.get("name") or "").strip()
    if who:
        lines.append("")
        lines.append(f"Nach Annehmen {top.get('ref')}:")
        lines.append(close_snippet_for_company(who))
    return "\n".join(lines).strip()


def get_lead(kind: str, lead_id: int) -> dict[str, Any] | None:
    con = _connect()
    try:
        if kind == "email":
            _ensure_agency(con)
            row = con.execute(
                "SELECT * FROM agency_leads WHERE id=?", (lead_id,)
            ).fetchone()
            if not row:
                return None
            d = _row(row)
            return {
                "ref": f"email:{lead_id}",
                "kind": "email",
                "id": lead_id,
                "name": d.get("name") or "",
                "email": d.get("email") or "",
                "phone": d.get("phone") or "",
                "company": d.get("company") or "",
                "intent": d.get("subject") or "",
                "notes": d.get("body_preview") or "",
                "source": "email_inbound",
            }
        if kind == "meta":
            _ensure_meta(con)
            row = con.execute(
                "SELECT * FROM meta_leads WHERE id=?", (lead_id,)
            ).fetchone()
            if not row:
                return None
            d = _row(row)
            if not inn.meta_tenant_allowed(str(d.get("tenant_id") or "")):
                raise PermissionError("Meta-Tenant nicht Agency-Sales")
            custom = d.get("custom_fields") or {}
            if isinstance(custom, str):
                try:
                    custom = json.loads(custom)
                except Exception:
                    custom = {}
            company = ""
            intent = ""
            if isinstance(custom, dict):
                company = str(
                    custom.get("company_name")
                    or custom.get("firma")
                    or custom.get("company")
                    or ""
                )
                intent = inn._intent_from_custom(custom)
            return {
                "ref": f"meta:{lead_id}",
                "kind": "meta",
                "id": lead_id,
                "name": d.get("full_name") or "",
                "email": d.get("email") or "",
                "phone": d.get("phone") or "",
                "company": company,
                "intent": intent or str(d.get("ad_name") or ""),
                "notes": json.dumps(custom, ensure_ascii=False)[:500]
                if custom
                else "",
                "source": "meta_inbound",
                "meta_lead_id": d.get("meta_lead_id"),
            }
    finally:
        con.close()
    return None


def mark_accepted(kind: str, lead_id: int, *, company_id: int) -> None:
    con = _connect()
    try:
        if kind == "email":
            _ensure_agency(con)
            con.execute(
                """UPDATE agency_leads SET status='accepted',
                   notes=COALESCE(notes,'') || ?,
                   updated_at=datetime('now') WHERE id=?""",
                (f"\n[Nils] CRM company_id={company_id}", lead_id),
            )
        elif kind == "meta":
            _ensure_meta(con)
            con.execute(
                """UPDATE meta_leads SET status='kontaktiert',
                   notes=COALESCE(notes,'') || ?,
                   updated_at=datetime('now') WHERE id=?""",
                (f"\n[Nils] angenommen CRM company_id={company_id}", lead_id),
            )
        con.commit()
    finally:
        con.close()


def accept_lead(kind: str, lead_id: int) -> dict[str, Any]:
    """Prospect + Follow-up-Notiz/Deal-Slot. Braucht Prospect- + Sales-Caps."""
    if not enabled():
        raise PermissionError("Inbound-Cap aus")
    if not prospect_svc.write_enabled():
        raise PermissionError("NILS_CAP_CRM_PROSPECT_CREATE aus")
    lead = get_lead(kind, lead_id)
    if not lead:
        raise ValueError(f"Lead {kind}:{lead_id} nicht gefunden")
    company_name = (
        (lead.get("company") or "").strip()
        or (lead.get("name") or "").strip()
        or (lead.get("email") or "").split("@")[0]
        or f"Inbound {kind}-{lead_id}"
    )
    contact = (lead.get("name") or "").strip()
    notes = (
        f"Inbound angenommen ({lead.get('source')})\n"
        f"Ref: {lead.get('ref')}\n"
        f"Intent: {lead.get('intent') or '—'}\n"
        f"Mail: {lead.get('email') or '—'}\n"
        f"Tel: {lead.get('phone') or '—'}\n"
        f"{lead.get('notes') or ''}"
    )[:2000]
    created = prospect_svc.create_prospect(
        company_name=company_name,
        contact_name=contact if contact != company_name else "",
        notes=notes,
        lead_source=str(lead.get("source") or "inbound")[:60],
    )
    company_id = int(getattr(created, "company_id", 0) or 0)
    if not company_id and isinstance(created, dict):
        company_id = int(created.get("company_id") or 0)
    if not company_id:
        raise RuntimeError("Prospect ohne company_id")

    next_action = "Inbound-Follow-up Call (<24h)"
    note_body = (
        f"Inbound angenommen {lead.get('ref')}: "
        f"{lead.get('intent') or 'Kontakt aufnehmen'}"
    )
    field = sales_svc.add_note(
        company_id=company_id,
        note=note_body,
        next_action=next_action,
    )
    mark_accepted(kind, lead_id, company_id=company_id)
    return {
        "lead": lead,
        "company_id": company_id,
        "company_name": company_name,
        "prospect": created,
        "field": field,
        "next_action": next_action,
    }


def close_snippet_for_company(company_name: str) -> str:
    """Copy-Paste Feld-Close nach Inbound-Annehmen (Zug O)."""
    try:
        from nils_job_runtime import crm_sales_field_service as crm

        mod = crm._load()
        return mod.feld_close_snippet(company_name or "")
    except Exception:
        name = (company_name or "").strip() or "Firma"
        return f"Feld-Close bei {name}\nnotiz: \nnächster Schritt: "


def format_accepted(result: dict[str, Any]) -> str:
    lead = result.get("lead") or {}
    company = str(result.get("company_name") or lead.get("company") or "").strip()
    lines = [
        "Inbound angenommen",
        f"Ref: {lead.get('ref')}",
        f"Firma: {company or '–'}",
        f"CRM company_id: {result.get('company_id')}",
        f"Follow-up: {result.get('next_action')}",
        "Deal/Notiz gesetzt — erscheint in Follow-up SLA / Pipeline heute.",
        "",
        "Close jetzt (Copy-Paste):",
        close_snippet_for_company(company),
        "",
        "Ausfüllen → senden → ja",
    ]
    return "\n".join(lines)


def format_approval(lead: dict[str, Any]) -> str:
    sc = inn.score_lead(
        name=str(lead.get("name") or ""),
        email=str(lead.get("email") or ""),
        phone=str(lead.get("phone") or ""),
        company=str(lead.get("company") or ""),
        intent=str(lead.get("intent") or ""),
    )
    return (
        "Freigabe nötig — Inbound annehmen:\n"
        f"Ref: {lead.get('ref')}\n"
        f"Firma/Name: {lead.get('company') or lead.get('name') or '—'}\n"
        f"Intent: {(lead.get('intent') or '—')[:100]}\n"
        f"Score: {sc}/100\n"
        f"Mail: {lead.get('email') or '—'} · Tel: {lead.get('phone') or '—'}\n"
        "Wirkung: Prospect + Deal-Follow-up (<24h)\n"
        'Antworte mit „ja“, sonst „stop“.'
    )

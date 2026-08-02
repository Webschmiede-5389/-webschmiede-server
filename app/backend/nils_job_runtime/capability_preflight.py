# -*- coding: utf-8 -*-
"""Capability preflight — real connector checks, never prompt self-assessment."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable


# Preflight outcomes (spec)
AVAILABLE = "AVAILABLE"
APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
NOT_CONFIGURED = "NOT_CONFIGURED"
CONNECTION_FAILED = "CONNECTION_FAILED"
PERMISSION_DENIED = "PERMISSION_DENIED"
DISABLED_BY_POLICY = "DISABLED_BY_POLICY"

EXECUTABLE_OUTCOMES = frozenset({AVAILABLE, APPROVAL_REQUIRED})


@dataclass
class PreflightResult:
    capability: str
    outcome: str
    detail: str = ""
    target_system: str = ""
    read_ok: bool = False
    write_ok: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def may_promise_execution(self) -> bool:
        return self.outcome in EXECUTABLE_OUTCOMES


def _env_truthy(name: str, default: str = "0") -> bool:
    return (os.getenv(name, default) or default).lower() not in (
        "0",
        "false",
        "no",
        "off",
        "",
    )


def _check_calendar(capability: str, *, write: bool) -> PreflightResult:
    # Staging: only AVAILABLE if explicit staging connector flag is set AND token present.
    # Never claim Google/Outlook from static prompt text.
    from nils_job_runtime.calendar_connector import (
        APPROVAL_MATRIX,
        CalendarConfig,
        inspect_auth,
    )

    cfg = CalendarConfig.from_env()
    target = cfg.target_name or cfg.test_calendar_id or "calendar"
    auth = inspect_auth(cfg)

    if not cfg.enabled:
        return PreflightResult(
            capability,
            DISABLED_BY_POLICY,
            "Kalender-Capability ist per Policy deaktiviert.",
            target_system=target,
            meta=auth,
        )
    if not cfg.allowed_calendar_id and not cfg.target_name:
        return PreflightResult(
            capability,
            NOT_CONFIGURED,
            "Kein Zielkalender konfiguriert (NILS_CALENDAR_TARGET / TEST_ID / BUSINESS_ID).",
            target_system="calendar",
            meta=auth,
        )
    if cfg.token_status == "missing":
        return PreflightResult(
            capability,
            NOT_CONFIGURED,
            "Kein gültiges Kalender-Token konfiguriert.",
            target_system=target,
            meta=auth,
        )
    if cfg.token_status == "expired":
        return PreflightResult(
            capability,
            CONNECTION_FAILED,
            "Kalender-Token abgelaufen oder ungültig.",
            target_system=target,
            meta=auth,
        )
    if cfg.token_status == "denied":
        return PreflightResult(
            capability,
            PERMISSION_DENIED,
            "Kalender-Berechtigung verweigert.",
            target_system=target,
            meta=auth,
        )
    if not cfg.allowed_calendar_id:
        return PreflightResult(
            capability,
            NOT_CONFIGURED,
            "Zielkalender-ID fehlt — Writes/Reads nur gegen Hold/Test oder webschmiede.",
            target_system=target,
            meta=auth,
        )

    # prepare = no write
    if capability == "calendar.prepare":
        return PreflightResult(
            capability,
            AVAILABLE,
            "Termin vorbereiten ohne Schreibaktion möglich.",
            target_system=target,
            read_ok=True,
            write_ok=False,
            meta=auth,
        )

    needs_approval = bool(APPROVAL_MATRIX.get(capability, {}).get("approval_required")) or write
    if needs_approval:
        return PreflightResult(
            capability,
            APPROVAL_REQUIRED,
            "Kalender-Schreibaktion erfordert ausdrückliche Freigabe (nur Testkalender).",
            target_system=target,
            read_ok=True,
            write_ok=False,
            meta=auth,
        )
    return PreflightResult(
        capability,
        AVAILABLE,
        "Kalender-Lesezugriff auf Testkalender technisch verfügbar.",
        target_system=target,
        read_ok=True,
        write_ok=False,
        meta=auth,
    )


def _check_email_send(capability: str) -> PreflightResult:
    # Generic email.send stays policy-blocked; use crm.email_send
    if capability == "email.send":
        return PreflightResult(
            capability,
            DISABLED_BY_POLICY,
            "Generisches email.send gesperrt — nutze CRM-Mail (Allowlist + Agency-SMTP).",
            target_system="email",
        )
    return _check_crm_email_send(capability)


def _check_crm_email_send(capability: str) -> PreflightResult:
    from nils_job_runtime import crm_email_service as mail

    if not mail.cap_enabled():
        return PreflightResult(
            capability,
            DISABLED_BY_POLICY,
            "CRM-E-Mail Cap aus (NILS_CAP_CRM_EMAIL / NILS_CAP_EMAIL_SEND).",
            target_system="email",
            read_ok=False,
            write_ok=False,
        )
    if not mail.allowlist():
        return PreflightResult(
            capability,
            NOT_CONFIGURED,
            "NILS_EMAIL_ALLOWLIST / AGENCY_OWNER_EMAIL fehlt.",
            target_system="email",
        )
    cfg = mail.resolve_agency_smtp()
    if cfg is None and not mail.dry_run():
        return PreflightResult(
            capability,
            NOT_CONFIGURED,
            "Agency-SMTP fehlt (AGENCY_SMTP_*/NILS_SMTP_* From @digitalehandwerkskunst.de). "
            "Oder NILS_EMAIL_DRY_RUN=1 für Test ohne Zustellung.",
            target_system="email",
        )
    detail = (
        "CRM-Mail Cap an; Dry-Run."
        if mail.dry_run() or cfg is None
        else f"Agency-SMTP ({cfg.source}) + Allowlist; Freigabe nötig."
    )
    return PreflightResult(
        capability,
        AVAILABLE,
        detail,
        target_system="smtp-agency",
        read_ok=True,
        write_ok=True,
    )


def _check_posting(capability: str, *, publish: bool) -> PreflightResult:
    if publish or capability == "posting.publish":
        if not _env_truthy("NILS_CAP_POSTING", "0"):
            return PreflightResult(
                capability,
                DISABLED_BY_POLICY,
                "Posting-Publish ist per Policy deaktiviert.",
                target_system="social",
            )
        return PreflightResult(
            capability,
            DISABLED_BY_POLICY,
            "Veröffentlichung in diesem Auftrag/Pfad verboten.",
            target_system="social",
        )

    # Read-only GGG check path (default enabled when sources exist)
    if (os.getenv("NILS_CAP_GGG_POSTING_CHECK", "1") or "1").lower() in (
        "0",
        "false",
        "off",
        "no",
    ):
        return PreflightResult(
            capability,
            DISABLED_BY_POLICY,
            "GGG Posting-Check per Policy deaktiviert.",
            target_system="ggg",
        )

    try:
        from nils_job_runtime import ggg_posting_check as ggg

        st = ggg.capability_status_from_inventory()
        if capability == "ggg.postings_find" or capability == "posting.find":
            outcome = st.get("ggg.postings_find") or st.get("posting.find") or "NOT_CONFIGURED"
        elif capability == "posting.text_check":
            outcome = st.get("posting.text_check") or "NOT_CONFIGURED"
        elif capability in ("posting.image_read", "posting.asset_check"):
            outcome = st.get("posting.asset_check") or st.get("posting.image_read") or "NOT_CONFIGURED"
        elif capability == "posting.visual_check":
            outcome = st.get("posting.visual_check") or "NOT_CONFIGURED"
        else:
            outcome = st.get("posting.check") or "NOT_CONFIGURED"

        if outcome in ("AVAILABLE", "DEGRADED"):
            return PreflightResult(
                capability,
                AVAILABLE,
                st.get("cause")
                or "GGG Read-only Posting-Quellen lesbar und Prüfung lauffähig.",
                target_system="ggg_local",
                read_ok=True,
                meta={"sample": st.get("sample_posting_id"), "sample_result": st.get("sample_result")},
            )
        if outcome == "CONNECTION_FAILED":
            return PreflightResult(
                capability,
                CONNECTION_FAILED,
                st.get("cause") or "GGG Connector-Ausfall",
                target_system="ggg_local",
                meta=st,
            )
        if outcome == "PERMISSION_DENIED":
            return PreflightResult(
                capability,
                PERMISSION_DENIED,
                "Keine Leseberechtigung auf GGG-Quellen.",
                target_system="ggg_local",
            )
        return PreflightResult(
            capability,
            NOT_CONFIGURED,
            "Keine GGG-Posting-Daten für Nils lesbar (Canva/Meta nicht angebunden).",
            target_system="ggg",
            meta=st,
        )
    except Exception as e:
        return PreflightResult(
            capability,
            CONNECTION_FAILED,
            f"GGG Preflight-Fehler: {type(e).__name__}: {e}",
            target_system="ggg",
        )


def _check_n8n(capability: str) -> PreflightResult:
    # Hard default: disabled — no uncontrolled n8n executions.
    if not _env_truthy("NILS_CAP_N8N", "0"):
        return PreflightResult(
            capability,
            DISABLED_BY_POLICY,
            "n8n-Ausführung ist per Policy deaktiviert.",
            target_system="n8n",
        )
    base = (os.getenv("N8N_BASE_URL") or "").strip()
    if not base:
        return PreflightResult(
            capability,
            NOT_CONFIGURED,
            "N8N_BASE_URL fehlt.",
            target_system="n8n",
        )
    return PreflightResult(
        capability,
        APPROVAL_REQUIRED,
        "n8n-Workflow-Start erfordert Freigabe.",
        target_system="n8n",
    )


def _check_shadow_echo(capability: str) -> PreflightResult:
    """Local/staging test capability — always available in isolated mode."""
    if _env_truthy("NILS_CONTROL_PLANE_STAGING", "1") or os.name == "nt":
        return PreflightResult(
            capability,
            AVAILABLE,
            "Lokale Shadow-/Staging-Capability verfügbar.",
            target_system="local-shadow",
            read_ok=True,
            write_ok=True,
        )
    return PreflightResult(
        capability,
        DISABLED_BY_POLICY,
        "Shadow-Echo nur in Staging.",
        target_system="local-shadow",
    )


def _check_crm_offer_read(capability: str) -> PreflightResult:
    """Read-only CRM offer path — isolated DB via NILS_CRM_DB / Postgres RO."""
    if not _env_truthy("NILS_CAP_CRM_READ", "1"):
        return PreflightResult(
            capability,
            DISABLED_BY_POLICY,
            "CRM-Lesen ist per Policy deaktiviert.",
            target_system="crm",
        )
    try:
        from nils_job_runtime import crm_offer_service as crm

        probe = crm.probe()
    except Exception as e:  # noqa: BLE001
        return PreflightResult(
            capability,
            CONNECTION_FAILED,
            f"CRM-Preflight-Fehler: {type(e).__name__}: {e}",
            target_system="crm",
        )
    outcome = probe.get("outcome") or (
        AVAILABLE if probe.get("ok") else CONNECTION_FAILED
    )
    return PreflightResult(
        capability,
        outcome if outcome in (
            AVAILABLE,
            NOT_CONFIGURED,
            CONNECTION_FAILED,
            DISABLED_BY_POLICY,
            APPROVAL_REQUIRED,
            PERMISSION_DENIED,
        ) else (AVAILABLE if probe.get("ok") else CONNECTION_FAILED),
        detail=str(probe.get("detail") or ""),
        target_system="crm",
        read_ok=bool(probe.get("ok")),
        write_ok=False,
        meta={k: v for k, v in probe.items() if k not in ("detail",)},
    )


def _check_crm_offer_pdf(capability: str) -> PreflightResult:
    if not _env_truthy("NILS_CAP_CRM_OFFER_PDF", "1"):
        return PreflightResult(
            capability,
            DISABLED_BY_POLICY,
            "CRM-Angebots-PDF ist per Policy deaktiviert.",
            target_system="crm+telegram",
        )
    base = _check_crm_offer_read("crm.offer_read")
    if not base.may_promise_execution:
        return PreflightResult(
            capability,
            base.outcome,
            base.detail,
            target_system="crm+telegram",
            read_ok=base.read_ok,
            write_ok=False,
            meta=base.meta,
        )
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    staging = _env_truthy("NILS_CONTROL_PLANE_STAGING", "1") or os.name == "nt"
    if not token and not staging:
        return PreflightResult(
            capability,
            NOT_CONFIGURED,
            "TELEGRAM_BOT_TOKEN fehlt für PDF-Versand.",
            target_system="telegram",
            read_ok=True,
        )
    return PreflightResult(
        capability,
        AVAILABLE,
        "CRM lesbar; PDF-Render lokal; Telegram sendDocument.",
        target_system="crm+telegram",
        read_ok=True,
        write_ok=False,
        meta=dict(base.meta or {}),
    )


def _check_crm_write_blocked(capability: str) -> PreflightResult:
    return PreflightResult(
        capability,
        DISABLED_BY_POLICY,
        "CRM-Schreiben ist deaktiviert (NILS_WRITE_ENABLED bleibt false).",
        target_system="crm",
        read_ok=False,
        write_ok=False,
    )


def _check_crm_sales_field(capability: str) -> PreflightResult:
    """Second-Manager sales field — gated by NILS_CAP_CRM_SALES_FIELD / per-cap."""
    from nils_job_runtime import crm_sales_field_service as sales

    if not sales.cap_enabled(capability):
        return PreflightResult(
            capability,
            DISABLED_BY_POLICY,
            "Sales-Field Cap aus (NILS_CAP_CRM_SALES_FIELD / per-cap).",
            target_system="crm",
            read_ok=False,
            write_ok=False,
        )
    base = _check_crm_offer_read("crm.offer_read")
    if not base.may_promise_execution:
        return PreflightResult(
            capability,
            base.outcome,
            base.detail,
            target_system="crm",
            read_ok=base.read_ok,
            write_ok=False,
            meta=dict(base.meta or {}),
        )
    write = capability in (
        "crm.note_create",
        "crm.deal_stage_update",
        "crm.deal_open",
        "crm.offer_write",
        "crm.deal_close",
    )
    return PreflightResult(
        capability,
        AVAILABLE,
        "CRM erreichbar; Sales-Field Cap an (Writes mit Freigabe).",
        target_system="crm",
        read_ok=True,
        write_ok=write,
        meta=dict(base.meta or {}),
    )


def _check_crm_inbound(capability: str, *, write: bool) -> PreflightResult:
    """Agency Inbound list/accept — Zug D."""
    from nils_job_runtime import inbound_service as inbound

    if not inbound.enabled():
        return PreflightResult(
            capability,
            DISABLED_BY_POLICY,
            "Inbound-Cap aus (NILS_CAP_CRM_INBOUND / Sales/Prospect).",
            target_system="agency_inbound",
            read_ok=False,
            write_ok=False,
        )
    if write:
        from nils_job_runtime import crm_prospect_service as prosp

        if not prosp.write_enabled():
            return PreflightResult(
                capability,
                DISABLED_BY_POLICY,
                "Annehmen braucht NILS_CAP_CRM_PROSPECT_CREATE.",
                target_system="agency_inbound",
                read_ok=True,
                write_ok=False,
            )
        return PreflightResult(
            capability,
            APPROVAL_REQUIRED,
            "Inbound annehmen nur mit Freigabe (Prospect + Follow-up).",
            target_system="agency_inbound",
            read_ok=True,
            write_ok=True,
            meta={"approval_required": True},
        )
    return PreflightResult(
        capability,
        AVAILABLE,
        "Inbound-Liste (Agency-Sales) lesbar.",
        target_system="agency_inbound",
        read_ok=True,
        write_ok=False,
    )


def _check_drive(capability: str, *, write: bool) -> PreflightResult:
    """Agency-Sales Drive Root — Zug F / SM-4."""
    from nils_job_runtime import drive_connector as drive

    cfg = drive.DriveConfig.from_env()
    if not cfg.enabled:
        return PreflightResult(
            capability,
            DISABLED_BY_POLICY,
            "Drive-Cap aus (NILS_CAP_DRIVE).",
            target_system="google_drive",
            read_ok=False,
            write_ok=False,
        )
    if not cfg.root_id:
        return PreflightResult(
            capability,
            NOT_CONFIGURED,
            "NILS_DRIVE_ROOT_ID fehlt.",
            target_system="google_drive",
            read_ok=False,
            write_ok=False,
        )
    meta: dict = {"approval_required": bool(write), "root_id_set": True}
    if write and capability == "drive.sheet_write":
        try:
            probe = drive.probe_sheets_api()
            meta["sheets_api"] = probe.get("status")
            if not probe.get("ok") and probe.get("status") == "api_not_enabled":
                meta["sheets_enable_url"] = probe.get("enable_url") or ""
        except Exception:
            meta["sheets_api"] = "probe_failed"
    if write:
        hint = f"Drive-Schreiben nur mit Freigabe im Ordner {cfg.root_name}."
        if meta.get("sheets_api") == "api_not_enabled":
            hint += (
                " Sheets-API noch aus — Append fällt auf neue Datei zurück. "
                f"Enable: {meta.get('sheets_enable_url') or 'GCP Console'}"
            )
        return PreflightResult(
            capability,
            APPROVAL_REQUIRED,
            hint,
            target_system="google_drive",
            read_ok=True,
            write_ok=True,
            meta=meta,
        )
    return PreflightResult(
        capability,
        AVAILABLE,
        f"Drive lesbar ({cfg.root_name}).",
        target_system="google_drive",
        read_ok=True,
        write_ok=False,
        meta={"root_id_set": True},
    )


def _check_crm_prospect_create(capability: str) -> PreflightResult:
    """Narrow write: PROSPECT only, gated by NILS_CAP_CRM_PROSPECT_CREATE."""
    from nils_job_runtime import crm_prospect_service as prosp

    if not prosp.write_enabled():
        return PreflightResult(
            capability,
            DISABLED_BY_POLICY,
            "Prospect-Create Cap aus (NILS_CAP_CRM_PROSPECT_CREATE).",
            target_system="crm",
            read_ok=False,
            write_ok=False,
        )
    base = _check_crm_offer_read("crm.offer_read")
    if not base.may_promise_execution:
        return PreflightResult(
            capability,
            base.outcome,
            base.detail,
            target_system="crm",
            read_ok=base.read_ok,
            write_ok=False,
            meta=dict(base.meta or {}),
        )
    return PreflightResult(
        capability,
        AVAILABLE,
        "CRM erreichbar; Prospect-Create Cap an (nur PROSPECT, Freigabe nötig).",
        target_system="crm",
        read_ok=True,
        write_ok=True,
        meta=dict(base.meta or {}),
    )


def _check_cursor_owner(capability: str) -> PreflightResult:
    allow = (os.getenv("NILS_CANARY_ALLOW_CURSOR", "0") or "0").lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
    if not allow:
        return PreflightResult(
            capability,
            DISABLED_BY_POLICY,
            "Cursor-Capability deaktiviert.",
            target_system="cursor",
        )
    return PreflightResult(
        capability,
        APPROVAL_REQUIRED if capability.endswith(".write") else AVAILABLE,
        "Cursor-Owner-Pfad.",
        target_system="cursor",
        read_ok=True,
        write_ok=capability.endswith(".write"),
    )


CapabilityChecker = Callable[[], PreflightResult]

REGISTRY: dict[str, CapabilityChecker] = {
    "calendar.read": lambda: _check_calendar("calendar.read", write=False),
    "calendar.freebusy": lambda: _check_calendar("calendar.freebusy", write=False),
    "calendar.availability": lambda: _check_calendar("calendar.availability", write=False),
    "calendar.prepare": lambda: _check_calendar("calendar.prepare", write=False),
    "calendar.create": lambda: _check_calendar("calendar.create", write=True),
    "calendar.update": lambda: _check_calendar("calendar.update", write=True),
    "calendar.delete": lambda: _check_calendar("calendar.delete", write=True),
    "calendar.invite": lambda: _check_calendar("calendar.invite", write=True),
    "calendar.write": lambda: _check_calendar("calendar.write", write=True),  # legacy alias
    "email.send": lambda: _check_email_send("email.send"),
    "posting.check": lambda: _check_posting("posting.check", publish=False),
    "posting.find": lambda: _check_posting("posting.find", publish=False),
    "posting.text_check": lambda: _check_posting("posting.text_check", publish=False),
    "posting.image_read": lambda: _check_posting("posting.image_read", publish=False),
    "posting.asset_check": lambda: _check_posting("posting.asset_check", publish=False),
    "posting.visual_check": lambda: _check_posting("posting.visual_check", publish=False),
    "ggg.postings_find": lambda: _check_posting("ggg.postings_find", publish=False),
    "posting.publish": lambda: _check_posting("posting.publish", publish=True),
    "n8n.execute": lambda: _check_n8n("n8n.execute"),
    "shadow.echo": lambda: _check_shadow_echo("shadow.echo"),
    "crm.offer_read": lambda: _check_crm_offer_read("crm.offer_read"),
    "crm.read": lambda: _check_crm_offer_read("crm.read"),
    "crm.customer_read": lambda: _check_crm_offer_read("crm.customer_read"),
    "crm.offer_pdf_send": lambda: _check_crm_offer_pdf("crm.offer_pdf_send"),
    "crm.prospect_create": lambda: _check_crm_prospect_create("crm.prospect_create"),
    "crm.email_send": lambda: _check_crm_email_send("crm.email_send"),
    "crm.pipeline_read": lambda: _check_crm_sales_field("crm.pipeline_read"),
    "crm.lead_thread": lambda: _check_crm_sales_field("crm.lead_thread"),
    "crm.note_create": lambda: _check_crm_sales_field("crm.note_create"),
    "crm.deal_stage_update": lambda: _check_crm_sales_field("crm.deal_stage_update"),
    "crm.deal_open": lambda: _check_crm_sales_field("crm.deal_open"),
    "crm.offer_write": lambda: _check_crm_sales_field("crm.offer_write"),
    "crm.deal_close": lambda: _check_crm_sales_field("crm.deal_close"),
    "crm.inbound_read": lambda: _check_crm_inbound("crm.inbound_read", write=False),
    "crm.inbound_accept": lambda: _check_crm_inbound("crm.inbound_accept", write=True),
    "drive.read": lambda: _check_drive("drive.read", write=False),
    "drive.list": lambda: _check_drive("drive.list", write=False),
    "drive.doc_create": lambda: _check_drive("drive.doc_create", write=True),
    "drive.sheet_create": lambda: _check_drive("drive.sheet_create", write=True),
    "drive.sheet_write": lambda: _check_drive("drive.sheet_write", write=True),
    "drive.write": lambda: _check_drive("drive.write", write=True),
    "crm.customer_write": lambda: _check_crm_write_blocked("crm.customer_write"),
    "cursor.read": lambda: _check_cursor_owner("cursor.read"),
    "cursor.write": lambda: _check_cursor_owner("cursor.write"),
}


# Action class → approval policy
READ_ACTIONS = frozenset({"read", "inspect", "check", "status", "question"})
PREPARE_ACTIONS = frozenset({"prepare", "draft", "plan"})
WRITE_ACTIONS = frozenset(
    {"write", "send", "publish", "delete", "execute", "create", "update"}
)


def run_preflight(capability: str) -> PreflightResult:
    checker = REGISTRY.get(capability)
    if checker is None:
        return PreflightResult(
            capability,
            NOT_CONFIGURED,
            f"Kein Connector/Tool für Capability '{capability}' registriert.",
        )
    try:
        return checker()
    except Exception as e:  # noqa: BLE001 — preflight must never crash the bot
        return PreflightResult(
            capability,
            CONNECTION_FAILED,
            f"Preflight-Fehler: {type(e).__name__}: {e}",
        )


def approval_needed(action_class: str, preflight: PreflightResult) -> str | None:
    """Return human-readable approval name if needed, else None."""
    ac = (action_class or "").lower().strip()
    if ac in READ_ACTIONS or ac in PREPARE_ACTIONS:
        if preflight.outcome == APPROVAL_REQUIRED:
            return f"Freigabe für {preflight.capability}"
        return None
    if ac in WRITE_ACTIONS or preflight.outcome == APPROVAL_REQUIRED:
        return f"Schreib-/Sendefreigabe für {preflight.capability}"
    if ac in ("blocked", "forbidden"):
        return f"Grundsätzlich gesperrt: {preflight.capability}"
    return None

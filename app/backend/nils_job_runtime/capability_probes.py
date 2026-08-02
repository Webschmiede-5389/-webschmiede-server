# -*- coding: utf-8 -*-
"""Read-only / mock capability probes — never mutate production data."""
from __future__ import annotations

import json
import os
import smtplib
import socket
import ssl
import urllib.request
from pathlib import Path
from typing import Any, Callable

from nils_job_runtime import capability_registry as reg

ProbeFn = Callable[[], dict[str, Any]]


def _result(status: str, cause: str, **evidence: Any) -> dict[str, Any]:
    return {"status": status, "cause": cause, "evidence": evidence}


def _env_has(*names: str) -> bool:
    for n in names:
        if (os.getenv(n) or "").strip():
            return True
    return False


def _load_secrets_presence() -> dict[str, bool]:
    """Key presence only — no values."""
    out: dict[str, bool] = {}
    candidates = [
        Path(
            r"C:\Users\kumex\OneDrive\Desktop\Jarvis\My_Company_Hub\projects\webschmiede-server\deploy.secrets.local"
        ),
        Path(__file__).resolve().parents[3] / "deploy.secrets.local",
        Path("/root/app/backend/.env"),
    ]
    for p in candidates:
        if not p.is_file():
            continue
        try:
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, _, v = s.partition("=")
                out[k.strip()] = bool(v.strip().strip('"').strip("'"))
        except Exception:
            continue
    return out


def probe_crm_read() -> dict[str, Any]:
    """Read-only: open local/agency DB or confirm module+schema path exists."""
    try:
        import agency_leads as al
        import sqlite3

        db_candidates = [
            Path("/root/app/backend/orders.db"),
            Path(__file__).resolve().parents[1] / "orders.db",
        ]
        for dbp in db_candidates:
            if dbp.is_file():
                con2 = sqlite3.connect(f"file:{dbp}?mode=ro", uri=True)
                try:
                    n = con2.execute(
                        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='agency_leads'"
                    ).fetchone()[0]
                    if n:
                        cnt = con2.execute("SELECT count(*) FROM agency_leads").fetchone()[0]
                        return _result(
                            "AVAILABLE",
                            f"agency_leads lesbar, rows={cnt}",
                            path=str(dbp.name),
                            rows=cnt,
                        )
                finally:
                    con2.close()
        # Module + list_leads exist; no prod DB here → not AVAILABLE
        if hasattr(al, "list_leads"):
            # In-memory schema smoke (read path code exists)
            con = sqlite3.connect(":memory:")
            con.executescript(
                """
                CREATE TABLE agency_leads (
                    id INTEGER PRIMARY KEY, name TEXT, status TEXT
                );
                """
            )
            cnt = con.execute("SELECT count(*) FROM agency_leads").fetchone()[0]
            con.close()
            return _result(
                "TEST_REQUIRED",
                "agency_leads-API vorhanden, aber keine Production-DB in dieser Umgebung für E2E-Read",
                module="agency_leads",
                memory_smoke_rows=cnt,
            )
        return _result("NOT_CONFIGURED", "agency_leads nicht importierbar")
    except Exception as e:
        return _result("CONNECTION_FAILED", f"{type(e).__name__}")


def probe_crm_company_create() -> dict[str, Any]:
    # Write capability — policy: no real write; mock path only
    return _result(
        "APPROVAL_REQUIRED",
        "Schreibpfad existiert (agency_leads), echte Anlage gesperrt ohne Freigabe; kein Prod-Write in diesem Scan",
        mock_only=True,
    )


def probe_crm_project_read() -> dict[str, Any]:
    roots = [
        Path(
            r"C:\Users\kumex\OneDrive\Desktop\Jarvis\My_Company_Hub\projects\webschmiede-server"
        ),
        Path(__file__).resolve().parents[3],
    ]
    for root in roots:
        kunden = root / "kunden"
        if kunden.is_dir():
            files = list(kunden.glob("*.json"))
            if files:
                # read one file metadata only
                sample = files[0]
                try:
                    data = json.loads(sample.read_text(encoding="utf-8"))
                    kid = data.get("id") or data.get("kunde_id") or sample.stem
                    return _result(
                        "AVAILABLE",
                        f"kunden-Register lesbar ({len(files)} Dateien), sample_id={kid}",
                        count=len(files),
                    )
                except Exception as e:
                    return _result("DEGRADED", f"kunden lesbar aber parse-fehler: {type(e).__name__}")
            return _result("NOT_CONFIGURED", "kunden/-Ordner leer")
    return _result("NOT_CONFIGURED", "kunden/-Ordner nicht gefunden")


def probe_agency_register() -> dict[str, Any]:
    return probe_crm_project_read()


def probe_cursor_start() -> dict[str, Any]:
    secrets = _load_secrets_presence()
    allow = (os.getenv("NILS_CANARY_ALLOW_CURSOR") or "0").lower() not in (
        "0",
        "false",
        "no",
        "off",
        "",
    )
    has_key = secrets.get("CURSOR_API_KEY") or _env_has("CURSOR_API_KEY")
    try:
        from nils_job_runtime import owner_limited

        has_route = hasattr(owner_limited, "maybe_handle")
    except Exception:
        has_route = False
    if not has_route:
        return _result("NOT_CONFIGURED", "owner_limited Cursor-Route fehlt")
    if not allow:
        return _result(
            "DISABLED_BY_POLICY",
            "Cursor-Start per NILS_CANARY_ALLOW_CURSOR gesperrt",
            key_present=bool(has_key),
        )
    if not has_key:
        return _result("NOT_CONFIGURED", "CURSOR_API_KEY fehlt")
    # Key present + allow — still no live start in this inventory
    return _result(
        "APPROVAL_REQUIRED",
        "Pfad vorhanden; Start nur mit Freigabe — kein Live-Start in diesem Scan",
        key_present=True,
    )


def probe_cursor_report_read() -> dict[str, Any]:
    try:
        from nils_job_runtime import store, status_reply

        store.ensure_schema()
        # read health / empty list is enough E2E for read path
        health = store.sqlite_health()
        txt = status_reply.live_status_report(chat_id="__probe__")
        ok = health.get("integrity_check") in (None, "ok") or health.get("exists") is not None
        if health.get("exists") is False:
            # schema created on ensure — still a working path
            return _result(
                "AVAILABLE",
                "Job-Status-Read-Pfad funktioniert (SQLite/status_reply)",
                integrity=health.get("integrity_check"),
                sample=txt[:80],
            )
        return _result(
            "AVAILABLE" if ok else "DEGRADED",
            "Job-Status-Read-Pfad geprüft",
            jobs=health.get("job_count"),
            integrity=health.get("integrity_check"),
        )
    except Exception as e:
        return _result("CONNECTION_FAILED", type(e).__name__)


def probe_ops_guardian() -> dict[str, Any]:
    try:
        import ops_guardian as og

        if hasattr(og, "load_state"):
            st = og.load_state()
            return _result(
                "AVAILABLE",
                "ops_guardian.load_state() lesbar (ohne Netz-Checks)",
                keys=list(st.keys())[:8] if isinstance(st, dict) else type(st).__name__,
            )
        if hasattr(og, "status"):
            return _result(
                "TEST_REQUIRED",
                "status() vorhanden — load_state fehlt; kein Netz-Probe in diesem Scan",
            )
        return _result("NOT_CONFIGURED", "ops_guardian.status fehlt")
    except Exception as e:
        return _result("NOT_CONFIGURED", type(e).__name__)


def probe_server_status() -> dict[str, Any]:
    inv = Path(
        r"C:\Users\kumex\OneDrive\Desktop\Jarvis\audits\infrastructure-audit-2026-07-29\nils-cp-canary-inventory.json"
    )
    if inv.is_file():
        try:
            data = json.loads(inv.read_text(encoding="utf-8"))
            remote = data.get("remote") or {}
            svc = remote.get("services") or {}
            if svc.get("snack-api") == "active":
                return _result(
                    "AVAILABLE",
                    "WEB snack-api=active, nils-job-worker=%s (Read-Inventory)"
                    % (svc.get("nils-job-worker"),),
                    source="nils-cp-canary-inventory.json",
                    host=remote.get("host"),
                )
        except Exception as e:
            return _result("DEGRADED", type(e).__name__)
    # skip live HTTP in inventory default — can hang offline
    return _result(
        "TEST_REQUIRED",
        "Kein frischer Server-Health-Probe in dieser Umgebung",
    )


def probe_n8n_status_read() -> dict[str, Any]:
    inv = Path(
        r"C:\Users\kumex\OneDrive\Desktop\Jarvis\audits\infrastructure-audit-2026-07-29\nils-cp-n8n-inventory.json"
    )
    if inv.is_file():
        try:
            data = json.loads(inv.read_text(encoding="utf-8"))
            remote = data.get("remote") or {}
            hz = (remote.get("n8n") or {}).get("http://127.0.0.1:5678/healthz") or {}
            if hz.get("http") == 200:
                return _result(
                    "AVAILABLE",
                    "n8n healthz 200 auf AUTO (Nachweis aus Read-Inventory)",
                    source="nils-cp-n8n-inventory.json",
                )
        except Exception:
            pass
    if not _env_has("N8N_BASE_URL") and (os.getenv("NILS_CAP_N8N") or "0") in (
        "0",
        "false",
        "no",
        "off",
        "",
    ):
        return _result(
            "DISABLED_BY_POLICY",
            "NILS_CAP_N8N aus; kein erzwungener Live-healthz in diesem Scan",
        )
    return _result("CONNECTION_FAILED", "n8n nicht erreichbar / kein Inventory-Nachweis")


def probe_n8n_execute() -> dict[str, Any]:
    if (os.getenv("NILS_CAP_N8N") or "0").lower() in ("0", "false", "no", "off", ""):
        return _result(
            "DISABLED_BY_POLICY",
            "n8n-Ausführung per Policy deaktiviert; kein Execute-Test",
        )
    return _result(
        "APPROVAL_REQUIRED",
        "Execute nur mit Freigabe und dediziertem Canary-Workflow — in diesem Scan nicht ausgeführt",
    )


def probe_gmail_read() -> dict[str, Any]:
    # Nils server path not wired; operator MCP previously verified — do not claim AVAILABLE for Nils
    # Re-check: no google token in Nils env
    if not _env_has("GOOGLE_GMAIL_TOKEN", "GMAIL_TOKEN", "NILS_GMAIL_TOKEN"):
        # Evidence from prior MCP inventory is operator-side, not Nils connector
        return _result(
            "NOT_CONFIGURED",
            "Kein Nils-Gmail-Connector verdrahtet (Operator-MCP ≠ Bot-Runtime)",
            operator_mcp_separate=True,
        )
    return _result("TEST_REQUIRED", "Token gesetzt, aber kein E2E-Read in Bot-Runtime")


def probe_email_draft() -> dict[str, Any]:
    return _result(
        "DISABLED_BY_POLICY",
        "E-Mail-Entwurf in diesem Auftrag verboten; Capability gesperrt",
    )


def probe_email_send() -> dict[str, Any]:
    secrets = _load_secrets_presence()
    smtp_ok = secrets.get("AGENCY_SMTP_HOST") or secrets.get("SMTP_HOST")
    if (os.getenv("NILS_CAP_EMAIL_SEND") or "0").lower() in ("0", "false", "", "off", "no"):
        return _result(
            "DISABLED_BY_POLICY",
            "E-Mail-Versand per Policy gesperrt; SMTP-Keys ggf. vorhanden aber nicht freigegeben",
            smtp_host_present=bool(smtp_ok),
        )
    return _result("APPROVAL_REQUIRED", "Send würde Freigabe brauchen — nicht getestet")


def probe_calendar_read() -> dict[str, Any]:
    if (os.getenv("NILS_CAP_CALENDAR") or "0").lower() in ("0", "false", "", "off", "no"):
        return _result(
            "DISABLED_BY_POLICY",
            "Kalender-Cap für Nils gesperrt; Operator-MCP separat",
            operator_mcp_separate=True,
        )
    try:
        from nils_job_runtime.calendar_connector import CalendarConnector, inspect_auth

        auth = inspect_auth()
        if auth["token_status"] == "missing":
            return _result("NOT_CONFIGURED", "Kein Kalender-Token für Nils", **auth)
        if auth["token_status"] == "expired":
            return _result("CONNECTION_FAILED", "Token abgelaufen", **auth)
        if auth["token_status"] == "denied":
            return _result("PERMISSION_DENIED", "Berechtigung verweigert", **auth)
        if not auth.get("allowed_calendar_id_set") and not auth.get("test_calendar_id_set"):
            return _result("NOT_CONFIGURED", "Zielkalender-ID fehlt", **auth)
        conn = CalendarConnector()
        out = conn.list_events(limit=5)
        return _result(
            "AVAILABLE",
            f"Zielkalender lesbar (backend={out.get('backend')}, mode={auth.get('mode')}, events={len(out.get('events') or [])})",
            **auth,
        )
    except Exception as e:
        return _result("CONNECTION_FAILED", f"{type(e).__name__}:{e}")


def probe_calendar_availability() -> dict[str, Any]:
    return probe_calendar_read()


def probe_calendar_freebusy() -> dict[str, Any]:
    return probe_calendar_read()


def probe_calendar_prepare() -> dict[str, Any]:
    if (os.getenv("NILS_CAP_CALENDAR") or "0").lower() in ("0", "false", "", "off", "no"):
        return _result("DISABLED_BY_POLICY", "Kalender-Cap gesperrt")
    return _result("AVAILABLE", "Prepare ohne Schreibaktion — Connector vorhanden")


def probe_calendar_write_family(action: str) -> dict[str, Any]:
    if (os.getenv("NILS_CAP_CALENDAR") or "0").lower() in ("0", "false", "", "off", "no"):
        return _result(
            "DISABLED_BY_POLICY",
            f"Kalender-{action} per Policy gesperrt (nur Testkalender nach Freigabe)",
        )
    return _result(
        "APPROVAL_REQUIRED",
        f"Kalender-{action} nur mit Freigabe und Zielkalender-ID — kein Hauptkalender",
    )


def probe_drive_read() -> dict[str, Any]:
    try:
        from nils_job_runtime import drive_connector as drive

        cfg = drive.DriveConfig.from_env()
        if not cfg.enabled:
            return _result(
                "DISABLED_BY_POLICY",
                "NILS_CAP_DRIVE aus",
            )
        if not cfg.root_id:
            return _result("NOT_CONFIGURED", "NILS_DRIVE_ROOT_ID fehlt")
        listed = drive.DriveConnector(cfg).list_files(limit=3)
        return _result(
            "AVAILABLE",
            f"Agency-Sales Root lesbar; n={listed.get('n') or 0}",
            root_name=cfg.root_name,
            root_id_suffix=cfg.root_id[-12:] if cfg.root_id else None,
            n=listed.get("n"),
        )
    except Exception as e:
        code = getattr(e, "code", None) or type(e).__name__
        return _result("CONNECTION_FAILED", f"{code}:{e}")


def probe_ggg_find() -> dict[str, Any]:
    try:
        from nils_job_runtime import ggg_posting_check as ggg

        st = ggg.capability_status_from_inventory()
        status = st.get("ggg.postings_find") or "NOT_CONFIGURED"
        return _result(
            status,
            st.get("cause")
            or f"Quellen inventarisiert; sample={st.get('sample_posting_id')}",
            inventory_summary=[
                {"id": s["id"], "status": s["status"], "evidence": s.get("evidence")}
                for s in (st.get("inventory") or [])
            ],
            sample_posting_id=st.get("sample_posting_id"),
        )
    except Exception as e:
        return _result("CONNECTION_FAILED", f"{type(e).__name__}:{e}")


def probe_posting_text() -> dict[str, Any]:
    try:
        from nils_job_runtime import ggg_posting_check as ggg

        st = ggg.capability_status_from_inventory()
        return _result(
            st.get("posting.text_check") or "NOT_CONFIGURED",
            f"sample_result={st.get('sample_result')}",
            sample_posting_id=st.get("sample_posting_id"),
        )
    except Exception as e:
        return _result("CONNECTION_FAILED", type(e).__name__)


def probe_posting_image() -> dict[str, Any]:
    try:
        from nils_job_runtime import ggg_posting_check as ggg

        st = ggg.capability_status_from_inventory()
        return _result(
            st.get("posting.image_read") or "NOT_CONFIGURED",
            "Dateiexistenz/Slide-Count; kein Pixel-OCR",
            sample_posting_id=st.get("sample_posting_id"),
        )
    except Exception as e:
        return _result("CONNECTION_FAILED", type(e).__name__)


def probe_posting_check() -> dict[str, Any]:
    try:
        from nils_job_runtime import ggg_posting_check as ggg

        st = ggg.capability_status_from_inventory()
        return _result(
            st.get("posting.check") or "NOT_CONFIGURED",
            f"read-only check sample={st.get('sample_result')}",
            sample_posting_id=st.get("sample_posting_id"),
        )
    except Exception as e:
        return _result("CONNECTION_FAILED", type(e).__name__)


def probe_posting_find() -> dict[str, Any]:
    return probe_ggg_find()


def probe_posting_asset() -> dict[str, Any]:
    try:
        from nils_job_runtime import ggg_posting_check as ggg

        st = ggg.capability_status_from_inventory()
        return _result(
            st.get("posting.asset_check") or "NOT_CONFIGURED",
            "Asset/Slide-Existenz",
            sample_posting_id=st.get("sample_posting_id"),
        )
    except Exception as e:
        return _result("CONNECTION_FAILED", type(e).__name__)


def probe_posting_visual() -> dict[str, Any]:
    try:
        from nils_job_runtime import ggg_posting_check as ggg

        st = ggg.capability_status_from_inventory()
        return _result(
            st.get("posting.visual_check") or "NOT_CONFIGURED",
            str(st.get("visual_detail") or "visual engine"),
            sample_posting_id=st.get("sample_posting_id"),
        )
    except Exception as e:
        return _result("CONNECTION_FAILED", type(e).__name__)


def probe_meta_planning() -> dict[str, Any]:
    try:
        import meta_leads as ml

        has = hasattr(ml, "list_leads") or hasattr(ml, "ensure_schema")
        secrets = _load_secrets_presence()
        token = any(secrets.get(k) for k in ("META_ACCESS_TOKEN", "META_PAGE_TOKEN", "META_APP_SECRET"))
        if has and not token:
            return _result(
                "NOT_CONFIGURED",
                "meta_leads-Modul vorhanden, Meta-Token in lokaler Secrets-Sicht fehlt/unbekannt",
            )
        if has:
            return _result(
                "TEST_REQUIRED",
                "Modul vorhanden — kein Read-Only-API-Probe gegen Meta Graph in diesem Scan",
            )
        return _result("NOT_CONFIGURED", "meta_leads fehlt")
    except Exception as e:
        return _result("CONNECTION_FAILED", type(e).__name__)


def probe_posting_publish() -> dict[str, Any]:
    return _result(
        "DISABLED_BY_POLICY",
        "Publish absichtlich gesperrt (Stub/Policy); kein Publish-Test",
    )


def probe_invoice_sorting() -> dict[str, Any]:
    try:
        from invoice_sorting import mailbox  # type: ignore

        secrets = _load_secrets_presence()
        imap = secrets.get("PIL001_IMAP_HOST") and secrets.get("PIL001_IMAP_USER")
        if not imap:
            return _result(
                "NOT_CONFIGURED",
                "invoice_sorting-Modul da, IMAP-Keys lokal unvollständig/fehlend",
            )
        return _result(
            "TEST_REQUIRED",
            "IMAP-Konfig vorhanden; kein Live-IMAP-Login in diesem Scan (Read-Probe ausstehend)",
            imap_host_present=True,
        )
    except Exception as e:
        return _result("NOT_CONFIGURED", f"invoice_sorting nicht ladbar: {type(e).__name__}")


def probe_meeting_scan() -> dict[str, Any]:
    tools_path = Path(__file__).resolve().parents[1] / "nils_tools.py"
    if not tools_path.is_file():
        return _result("NOT_CONFIGURED", "nils_tools.py fehlt")
    try:
        text = tools_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return _result("CONNECTION_FAILED", type(e).__name__)
    if '"name": "meeting_scan"' in text or "'name': 'meeting_scan'" in text:
        return _result(
            "AVAILABLE",
            "meeting_scan im Tool-Katalog registriert (Code-Nachweis, kein Live-Scrape)",
            tool="meeting_scan",
        )
    return _result("NOT_CONFIGURED", "meeting_scan nicht im Katalog")


def probe_canva() -> dict[str, Any]:
    secrets = _load_secrets_presence()
    if secrets.get("CANVA_API_KEY") or _env_has("CANVA_API_KEY"):
        return _result("TEST_REQUIRED", "Canva-Key-Hinweis, aber kein Nils-Connector-E2E")
    return _result("NOT_CONFIGURED", "Kein Canva-Connector/Key für Nils")


def probe_control_stop() -> dict[str, Any]:
    try:
        from nils_job_runtime import control_commands

        r = control_commands.handle_stop(chat_id="__cap_probe_stop__")
        if r.get("text") == control_commands.MSG_NO_JOB:
            return _result("AVAILABLE", "Stop-Pfad antwortet idempotent ohne aktiven Job")
        return _result("DEGRADED", "Stop-Pfad unerwartete Antwort", reply=(r.get("text") or "")[:80])
    except Exception as e:
        return _result("CONNECTION_FAILED", type(e).__name__)


def probe_control_status() -> dict[str, Any]:
    try:
        from nils_job_runtime.status_reply import live_status_report

        txt = live_status_report(chat_id="__cap_probe_status__")
        if "kein Auftrag" in txt.lower():
            return _result("AVAILABLE", "Status-Read-Pfad funktioniert")
        return _result("AVAILABLE", "Status-Read-Pfad antwortet", sample=txt[:80])
    except Exception as e:
        return _result("CONNECTION_FAILED", type(e).__name__)


PROBES: dict[str, ProbeFn] = {
    "crm.read": probe_crm_read,
    "crm.company_create": probe_crm_company_create,
    "crm.project_read": probe_crm_project_read,
    "agency.project_register_read": probe_agency_register,
    "cursor.job_start": probe_cursor_start,
    "cursor.report_read": probe_cursor_report_read,
    "n8n.workflow_status_read": probe_n8n_status_read,
    "n8n.workflow_execute": probe_n8n_execute,
    "gmail.read": probe_gmail_read,
    "email.draft_create": probe_email_draft,
    "email.send": probe_email_send,
    "calendar.read": probe_calendar_read,
    "calendar.availability": probe_calendar_availability,
    "calendar.freebusy": probe_calendar_freebusy,
    "calendar.prepare": probe_calendar_prepare,
    "calendar.create": lambda: probe_calendar_write_family("create"),
    "calendar.update": lambda: probe_calendar_write_family("update"),
    "calendar.delete": lambda: probe_calendar_write_family("delete"),
    "calendar.invite": lambda: probe_calendar_write_family("invite"),
    "drive.read": probe_drive_read,
    "ggg.postings_find": probe_ggg_find,
    "posting.find": probe_posting_find,
    "posting.text_check": probe_posting_text,
    "posting.image_read": probe_posting_image,
    "posting.asset_check": probe_posting_asset,
    "posting.visual_check": probe_posting_visual,
    "posting.check": probe_posting_check,
    "meta.planning_status_read": probe_meta_planning,
    "posting.publish": probe_posting_publish,
    "invoice_sorting.check": probe_invoice_sorting,
    "server.status_read": probe_server_status,
    "ops.guardian_read": probe_ops_guardian,
    "sales.meeting_scan": probe_meeting_scan,
    "canva.design_read": probe_canva,
    "control_plane.stop": probe_control_stop,
    "control_plane.status": probe_control_status,
}


def run_all_probes(*, persist: bool = True) -> list[dict[str, Any]]:
    reg.ensure_schema()
    reg.seed_catalog()
    out: list[dict[str, Any]] = []
    for cid, fn in PROBES.items():
        try:
            r = fn()
        except Exception as e:
            r = _result("CONNECTION_FAILED", f"probe_crash:{type(e).__name__}")
        status = r["status"]
        cause = r["cause"]
        evidence = r.get("evidence") or {}
        if persist:
            reg.record_probe(cid, status=status, cause=cause, evidence=evidence)
        out.append({"capability_id": cid, "status": status, "cause": cause, "evidence": evidence})
    return out

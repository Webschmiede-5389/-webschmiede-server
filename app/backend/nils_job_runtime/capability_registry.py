# -*- coding: utf-8 -*-
"""Persistent Nils capability registry — status only from verified probes."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATUSES = frozenset(
    {
        "AVAILABLE",
        "APPROVAL_REQUIRED",
        "NOT_CONFIGURED",
        "CONNECTION_FAILED",
        "TOKEN_EXPIRED",
        "PERMISSION_DENIED",
        "DISABLED_BY_POLICY",
        "TEST_REQUIRED",
        "DEGRADED",
    }
)

# Human buckets for „Was kannst du aktuell?“
BUCKETS = {
    "AVAILABLE": "verfügbar",
    "APPROVAL_REQUIRED": "nur mit Freigabe",
    "NOT_CONFIGURED": "nicht eingerichtet",
    "CONNECTION_FAILED": "derzeit fehlerhaft",
    "TOKEN_EXPIRED": "derzeit fehlerhaft",
    "PERMISSION_DENIED": "derzeit fehlerhaft",
    "DISABLED_BY_POLICY": "absichtlich gesperrt",
    "TEST_REQUIRED": "nicht eingerichtet",
    "DEGRADED": "derzeit fehlerhaft",
}

_LOCK = threading.RLock()

# Catalog: minimum + related capabilities (definitions only — status from probes)
CATALOG: list[dict[str, Any]] = [
    {
        "capability_id": "crm.read",
        "name": "CRM lesen",
        "description": "Agency-Leads / Kontakte aus SQLite lesen",
        "target_system": "orders.db / agency_leads",
        "access": "read",
        "permission_needed": "db_read",
        "approval_needed": False,
        "connector": "sqlite_agency",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "crm.company_create",
        "name": "CRM-Unternehmen anlegen",
        "description": "Neues Unternehmen/Lead anlegen",
        "target_system": "agency_leads",
        "access": "write",
        "permission_needed": "db_write",
        "approval_needed": True,
        "connector": "sqlite_agency",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "crm.project_read",
        "name": "CRM-Projekt lesen",
        "description": "Unternehmen/Kontakte im CRM lesen (Lead/Prospect/Customer)",
        "target_system": "kunden.json + orders.db",
        "access": "read",
        "permission_needed": "db_read",
        "approval_needed": False,
        "connector": "kunden_registry",
        "projects": ["agency", "*"],
        "users": ["owner"],
    },
    {
        "capability_id": "agency.project_register_read",
        "name": "Agency-Projektregister lesen",
        "description": "kunden/*.json Projektregister",
        "target_system": "kunden/",
        "access": "read",
        "permission_needed": "fs_read",
        "approval_needed": False,
        "connector": "filesystem",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "cursor.job_start",
        "name": "Cursor-Job starten",
        "description": "Owner-Limited cursorjob / Cursor-Agent",
        "target_system": "cursor",
        "access": "write",
        "permission_needed": "cursor_api",
        "approval_needed": True,
        "connector": "nils_job_runtime.owner_limited",
        "projects": ["agency", "canary"],
        "users": ["owner"],
    },
    {
        "capability_id": "cursor.report_read",
        "name": "Cursor-Bericht lesen",
        "description": "jobstatus / jobinspect aus SQLite",
        "target_system": "nils-runtime.db",
        "access": "read",
        "permission_needed": "db_read",
        "approval_needed": False,
        "connector": "nils_job_runtime",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "n8n.workflow_status_read",
        "name": "n8n-Workflowstatus lesen",
        "description": "n8n Health / Workflow-Metadaten lesen",
        "target_system": "n8n",
        "access": "read",
        "permission_needed": "n8n_read",
        "approval_needed": False,
        "connector": "n8n_http",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "n8n.workflow_execute",
        "name": "n8n-Workflow ausführen",
        "description": "Workflow triggern",
        "target_system": "n8n",
        "access": "write",
        "permission_needed": "n8n_execute",
        "approval_needed": True,
        "connector": "n8n_http",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "gmail.read",
        "name": "Gmail lesen",
        "description": "Postfach/Labels lesen",
        "target_system": "gmail",
        "access": "read",
        "permission_needed": "gmail_read",
        "approval_needed": False,
        "connector": "google_workspace",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "email.draft_create",
        "name": "E-Mail-Entwurf erstellen",
        "description": "Draft ohne Versand",
        "target_system": "gmail/smtp",
        "access": "write",
        "permission_needed": "mail_draft",
        "approval_needed": True,
        "connector": "google_workspace",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "email.send",
        "name": "E-Mail versenden",
        "description": "Echte Mail senden",
        "target_system": "smtp/gmail",
        "access": "write",
        "permission_needed": "mail_send",
        "approval_needed": True,
        "connector": "smtp",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "calendar.read",
        "name": "Kalender lesen",
        "description": "Testkalender Events lesen",
        "target_system": "google_calendar_test",
        "access": "read",
        "permission_needed": "calendar_read",
        "approval_needed": False,
        "connector": "nils_calendar",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "calendar.freebusy",
        "name": "Free/Busy prüfen",
        "description": "Freie/belegte Zeiten im Testkalender",
        "target_system": "google_calendar_test",
        "access": "read",
        "permission_needed": "calendar_read",
        "approval_needed": False,
        "connector": "nils_calendar",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "calendar.availability",
        "name": "Verfügbarkeit prüfen",
        "description": "Alias zu freebusy",
        "target_system": "google_calendar_test",
        "access": "read",
        "permission_needed": "calendar_read",
        "approval_needed": False,
        "connector": "nils_calendar",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "calendar.prepare",
        "name": "Termin vorbereiten",
        "description": "Payload bauen ohne Schreibaktion",
        "target_system": "google_calendar_test",
        "access": "read",
        "permission_needed": "calendar_read",
        "approval_needed": False,
        "connector": "nils_calendar",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "calendar.create",
        "name": "Termin erstellen",
        "description": "Event nur im Testkalender anlegen",
        "target_system": "google_calendar_test",
        "access": "write",
        "permission_needed": "calendar_write",
        "approval_needed": True,
        "connector": "nils_calendar",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "calendar.update",
        "name": "Termin ändern",
        "description": "Event im Testkalender ändern",
        "target_system": "google_calendar_test",
        "access": "write",
        "permission_needed": "calendar_write",
        "approval_needed": True,
        "connector": "nils_calendar",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "calendar.delete",
        "name": "Termin löschen",
        "description": "Event im Testkalender löschen",
        "target_system": "google_calendar_test",
        "access": "write",
        "permission_needed": "calendar_write",
        "approval_needed": True,
        "connector": "nils_calendar",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "calendar.invite",
        "name": "Teilnehmer einladen",
        "description": "Einladung nur mit Freigabe (Testkalender)",
        "target_system": "google_calendar_test",
        "access": "write",
        "permission_needed": "calendar_invite",
        "approval_needed": True,
        "connector": "nils_calendar",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "drive.read",
        "name": "Agency-Sales Drive lesen",
        "description": "Dateien im Agency-Sales-Root listen (kein anderer Ordner)",
        "target_system": "google_drive",
        "access": "read",
        "permission_needed": "drive_read",
        "approval_needed": False,
        "connector": "nils_drive",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "drive.doc_create",
        "name": "Drive Kurzdoc anlegen",
        "description": "Google Doc nur im Agency-Sales-Root, mit Freigabe",
        "target_system": "google_drive",
        "access": "write",
        "permission_needed": "drive_write",
        "approval_needed": True,
        "connector": "nils_drive",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "drive.sheet_create",
        "name": "Drive Tabelle anlegen",
        "description": "Leere Spreadsheet nur im Agency-Sales-Root, mit Freigabe",
        "target_system": "google_drive",
        "access": "write",
        "permission_needed": "drive_write",
        "approval_needed": True,
        "connector": "nils_drive",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "drive.sheet_write",
        "name": "Drive Tabelle Zeilen schreiben",
        "description": "Zeilen in Agency-Sales-Tabelle (append oder neu mit CSV)",
        "target_system": "google_drive",
        "access": "write",
        "permission_needed": "drive_write",
        "approval_needed": True,
        "connector": "nils_drive",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "drive.write",
        "name": "Drive schreiben (Alias)",
        "description": "Alias für Doc/Tabelle im Agency-Sales-Root",
        "target_system": "google_drive",
        "access": "write",
        "permission_needed": "drive_write",
        "approval_needed": True,
        "connector": "nils_drive",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "ggg.postings_find",
        "name": "GGG-Postings finden",
        "description": "Geplante/lokale GGG-Postings in Hub/Planner finden (read-only)",
        "target_system": "ggg_local",
        "access": "read",
        "permission_needed": "fs_read",
        "approval_needed": False,
        "connector": "ggg_posting_check",
        "projects": ["German Golf Guide"],
        "users": ["owner"],
    },
    {
        "capability_id": "posting.text_check",
        "name": "Posting-Texte prüfen",
        "description": "Caption/Editorial gegen GGG-Kriterien (read-only)",
        "target_system": "ggg_local",
        "access": "read",
        "permission_needed": "fs_read",
        "approval_needed": False,
        "connector": "ggg_posting_check",
        "projects": ["German Golf Guide", "agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "posting.image_read",
        "name": "Posting-Bilder lesen",
        "description": "Slide-/Story-Dateien existenz-/count-prüfen (kein Publish)",
        "target_system": "ggg_local",
        "access": "read",
        "permission_needed": "fs_read",
        "approval_needed": False,
        "connector": "ggg_posting_check",
        "projects": ["German Golf Guide"],
        "users": ["owner"],
    },
    {
        "capability_id": "posting.check",
        "name": "Posting prüfen",
        "description": "GGG Posting Gesamtprüfung (Text+Asset+optional Visual, read-only)",
        "target_system": "ggg_local",
        "access": "read",
        "permission_needed": "fs_read",
        "approval_needed": False,
        "connector": "ggg_posting_check",
        "projects": ["German Golf Guide", "agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "posting.find",
        "name": "Postings finden",
        "description": "Alias zu ggg.postings_find",
        "target_system": "ggg_local",
        "access": "read",
        "permission_needed": "fs_read",
        "approval_needed": False,
        "connector": "ggg_posting_check",
        "projects": ["German Golf Guide"],
        "users": ["owner"],
    },
    {
        "capability_id": "posting.asset_check",
        "name": "Posting-Assets prüfen",
        "description": "Datei-/Slide-Existenz und Dimensionen (read-only)",
        "target_system": "ggg_local",
        "access": "read",
        "permission_needed": "fs_read",
        "approval_needed": False,
        "connector": "ggg_posting_check",
        "projects": ["German Golf Guide"],
        "users": ["owner"],
    },
    {
        "capability_id": "posting.visual_check",
        "name": "Posting visuell prüfen",
        "description": "OCR/OpenCV Qualitätskontrolle der PNGs (read-only)",
        "target_system": "ggg_local",
        "access": "read",
        "permission_needed": "fs_read",
        "approval_needed": False,
        "connector": "ggg_visual_check",
        "projects": ["German Golf Guide"],
        "users": ["owner"],
    },
    {
        "capability_id": "meta.planning_status_read",
        "name": "Meta-Planungsstatus lesen",
        "description": "Meta Lead/Campaign Status lesen",
        "target_system": "meta",
        "access": "read",
        "permission_needed": "meta_read",
        "approval_needed": False,
        "connector": "meta_graph",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "posting.publish",
        "name": "Posting veröffentlichen",
        "description": "Social Publish",
        "target_system": "meta/instagram",
        "access": "write",
        "permission_needed": "meta_publish",
        "approval_needed": True,
        "connector": "meta_graph",
        "projects": ["agency", "German Golf Guide"],
        "users": ["owner"],
    },
    {
        "capability_id": "invoice_sorting.check",
        "name": "Belegsortierung prüfen",
        "description": "PIL001/Invoice-Sorting Status prüfen",
        "target_system": "invoice_sorting",
        "access": "read",
        "permission_needed": "imap_or_fs_read",
        "approval_needed": False,
        "connector": "invoice_sorting",
        "projects": ["agency", "Belegsortierung"],
        "users": ["owner"],
    },
    {
        "capability_id": "server.status_read",
        "name": "Serverstatus lesen",
        "description": "snack-api / Worker / Health",
        "target_system": "web-01neu",
        "access": "read",
        "permission_needed": "ssh_or_http",
        "approval_needed": False,
        "connector": "ops",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "ops.guardian_read",
        "name": "Ops-Guardian lesen",
        "description": "Guardian-Status lesen",
        "target_system": "ops_guardian",
        "access": "read",
        "permission_needed": "api_read",
        "approval_needed": False,
        "connector": "ops_guardian",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "sales.meeting_scan",
        "name": "Meeting-Scan",
        "description": "Website scannen + Angebotsentwurf (ohne Kundenmail)",
        "target_system": "akquise",
        "access": "read",
        "permission_needed": "http_read",
        "approval_needed": False,
        "connector": "nils_tools.meeting_scan",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "canva.design_read",
        "name": "Canva lesen",
        "description": "Canva-Designs lesen",
        "target_system": "canva",
        "access": "read",
        "permission_needed": "canva_api",
        "approval_needed": False,
        "connector": "canva",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "control_plane.stop",
        "name": "Stop/Abbruch",
        "description": "Aktiven Job abbrechen",
        "target_system": "nils_job_runtime",
        "access": "write",
        "permission_needed": "owner_chat",
        "approval_needed": False,
        "connector": "control_plane",
        "projects": ["agency"],
        "users": ["owner"],
    },
    {
        "capability_id": "control_plane.status",
        "name": "Job-Status abfragen",
        "description": "Was machst du gerade / jobstatus",
        "target_system": "nils_job_runtime",
        "access": "read",
        "permission_needed": "owner_chat",
        "approval_needed": False,
        "connector": "control_plane",
        "projects": ["agency"],
        "users": ["owner"],
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def db_path() -> Path:
    raw = os.getenv("NILS_CAPABILITY_REGISTRY_DB")
    if raw:
        return Path(raw)
    # Prefer next to runtime DB
    try:
        from nils_job_runtime import store

        p = store.db_path().parent / "nils-capability-registry.db"
        return p
    except Exception:
        pass
    if os.name == "nt":
        return (
            Path(__file__).resolve().parents[3]
            / "agency"
            / "nils-capability-registry.db"
        )
    return Path("/var/lib/webschmiede/nils-capability-registry.db")


def connect() -> sqlite3.Connection:
    p = db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p), timeout=30, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=5000")
    return con


SCHEMA = """
CREATE TABLE IF NOT EXISTS nils_capabilities (
    capability_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    target_system TEXT NOT NULL DEFAULT '',
    access_mode TEXT NOT NULL DEFAULT 'read',
    permission_needed TEXT NOT NULL DEFAULT '',
    approval_needed INTEGER NOT NULL DEFAULT 0,
    connector TEXT NOT NULL DEFAULT '',
    last_tested_at TEXT,
    last_test_status TEXT NOT NULL DEFAULT 'TEST_REQUIRED',
    technical_cause TEXT,
    projects_json TEXT NOT NULL DEFAULT '[]',
    users_json TEXT NOT NULL DEFAULT '[]',
    evidence_json TEXT NOT NULL DEFAULT '{}',
    stale_after_hours INTEGER NOT NULL DEFAULT 72,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS nils_capability_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    capability_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL
);
"""


def ensure_schema() -> Path:
    with _LOCK:
        con = connect()
        try:
            con.executescript(SCHEMA)
            con.commit()
        finally:
            con.close()
    return db_path()


def seed_catalog(*, reset_status: bool = False) -> int:
    """Upsert catalog definitions. Does not invent AVAILABLE."""
    ensure_schema()
    now = utc_now()
    n = 0
    with _LOCK:
        con = connect()
        try:
            for c in CATALOG:
                row = con.execute(
                    "SELECT capability_id, last_test_status FROM nils_capabilities WHERE capability_id=?",
                    (c["capability_id"],),
                ).fetchone()
                if row is None:
                    con.execute(
                        """
                        INSERT INTO nils_capabilities (
                            capability_id, name, description, target_system, access_mode,
                            permission_needed, approval_needed, connector,
                            last_tested_at, last_test_status, technical_cause,
                            projects_json, users_json, evidence_json, updated_at
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            c["capability_id"],
                            c["name"],
                            c["description"],
                            c["target_system"],
                            c["access"],
                            c["permission_needed"],
                            1 if c.get("approval_needed") else 0,
                            c["connector"],
                            None,
                            "TEST_REQUIRED",
                            "Noch nicht Ende-zu-Ende geprüft",
                            json.dumps(c.get("projects") or [], ensure_ascii=False),
                            json.dumps(c.get("users") or [], ensure_ascii=False),
                            "{}",
                            now,
                        ),
                    )
                    n += 1
                else:
                    status = "TEST_REQUIRED" if reset_status else row["last_test_status"]
                    con.execute(
                        """
                        UPDATE nils_capabilities SET
                            name=?, description=?, target_system=?, access_mode=?,
                            permission_needed=?, approval_needed=?, connector=?,
                            projects_json=?, users_json=?,
                            last_test_status=CASE WHEN ? THEN 'TEST_REQUIRED' ELSE last_test_status END,
                            updated_at=?
                        WHERE capability_id=?
                        """,
                        (
                            c["name"],
                            c["description"],
                            c["target_system"],
                            c["access"],
                            c["permission_needed"],
                            1 if c.get("approval_needed") else 0,
                            c["connector"],
                            json.dumps(c.get("projects") or [], ensure_ascii=False),
                            json.dumps(c.get("users") or [], ensure_ascii=False),
                            1 if reset_status else 0,
                            now,
                            c["capability_id"],
                        ),
                    )
            con.commit()
        finally:
            con.close()
    return n


def record_probe(
    capability_id: str,
    *,
    status: str,
    cause: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if status not in STATUSES:
        raise ValueError(f"invalid_status:{status}")
    ensure_schema()
    now = utc_now()
    ev = evidence or {}
    # Never store secrets
    for k in list(ev.keys()):
        lk = k.lower()
        if any(x in lk for x in ("token", "password", "secret", "api_key", "pass")):
            ev[k] = "***"
    with _LOCK:
        con = connect()
        try:
            row = con.execute(
                "SELECT * FROM nils_capabilities WHERE capability_id=?",
                (capability_id,),
            ).fetchone()
            if not row:
                raise KeyError(capability_id)
            con.execute(
                """
                UPDATE nils_capabilities SET
                    last_tested_at=?, last_test_status=?, technical_cause=?,
                    evidence_json=?, updated_at=?
                WHERE capability_id=?
                """,
                (
                    now,
                    status,
                    (cause or "")[:500],
                    json.dumps(ev, ensure_ascii=False)[:2000],
                    now,
                    capability_id,
                ),
            )
            con.execute(
                "INSERT INTO nils_capability_events (capability_id, event_type, detail, created_at) VALUES (?,?,?,?)",
                (capability_id, "probe", f"{status}:{(cause or '')[:200]}", now),
            )
            con.commit()
            return get(capability_id)  # type: ignore[return-value]
        finally:
            con.close()


def get(capability_id: str) -> dict[str, Any] | None:
    ensure_schema()
    con = connect()
    try:
        row = con.execute(
            "SELECT * FROM nils_capabilities WHERE capability_id=?",
            (capability_id,),
        ).fetchone()
        return _row(row)
    finally:
        con.close()


def list_all() -> list[dict[str, Any]]:
    ensure_schema()
    con = connect()
    try:
        rows = con.execute(
            "SELECT * FROM nils_capabilities ORDER BY capability_id"
        ).fetchall()
        return [_row(r) for r in rows if r]
    finally:
        con.close()


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    d = dict(row)
    try:
        d["projects"] = json.loads(d.get("projects_json") or "[]")
    except Exception:
        d["projects"] = []
    try:
        d["users"] = json.loads(d.get("users_json") or "[]")
    except Exception:
        d["users"] = []
    try:
        d["evidence"] = json.loads(d.get("evidence_json") or "{}")
    except Exception:
        d["evidence"] = {}
    d["approval_needed"] = bool(d.get("approval_needed"))
    d["stale"] = is_stale(d)
    d["effective_status"] = "TEST_REQUIRED" if d["stale"] and d.get("last_test_status") == "AVAILABLE" else d.get("last_test_status")
    # If stale AVAILABLE → surface as DEGRADED visibility via effective
    if d["stale"] and d.get("last_test_status") in ("AVAILABLE", "APPROVAL_REQUIRED"):
        d["effective_status"] = "DEGRADED"
        d["stale_note"] = "Teststatus veraltet — erneute Prüfung erforderlich"
    return d


def is_stale(cap: dict[str, Any]) -> bool:
    ts = cap.get("last_tested_at")
    if not ts:
        return True
    try:
        tested = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        age_h = (datetime.now(timezone.utc) - tested).total_seconds() / 3600.0
        return age_h > float(cap.get("stale_after_hours") or 72)
    except Exception:
        return True


def allowed_for_project(cap: dict[str, Any], project: str | None) -> bool:
    projects = cap.get("projects") or []
    if not projects or "*" in projects:
        return True
    if not project:
        return True
    return project in projects or any(project.lower() == p.lower() for p in projects)


def format_capability_report(*, project: str | None = None) -> str:
    """Live answer for „Was kannst du aktuell?“ — only from registry."""
    caps = list_all()
    if not caps:
        return (
            "Capability-Registry ist leer. Noch keine geprüften Fähigkeiten. "
            "Sage „Capability-Scan“, dann prüfe ich den Bestand."
        )
    buckets: dict[str, list[str]] = {
        "verfügbar": [],
        "nur mit Freigabe": [],
        "nicht eingerichtet": [],
        "derzeit fehlerhaft": [],
        "absichtlich gesperrt": [],
    }
    for c in caps:
        if project and not allowed_for_project(c, project):
            continue
        st = c.get("effective_status") or c.get("last_test_status") or "TEST_REQUIRED"
        bucket = BUCKETS.get(st, "nicht eingerichtet")
        note = ""
        if c.get("stale") and c.get("stale_note"):
            note = " (Test veraltet)"
        cause = (c.get("technical_cause") or "")[:80]
        line = f"• {c['name']} [{st}]{note}"
        if cause and st not in ("AVAILABLE",):
            line += f" — {cause}"
        buckets[bucket].append(line)

    lines = ["Was ich aktuell wirklich kann (aus der geprüften Registry):", ""]
    for title in (
        "verfügbar",
        "nur mit Freigabe",
        "absichtlich gesperrt",
        "nicht eingerichtet",
        "derzeit fehlerhaft",
    ):
        items = buckets.get(title) or []
        lines.append(f"{title.upper()}:")
        if not items:
            lines.append("• —")
        else:
            lines.extend(items)
        lines.append("")
    lines.append(
        "Keine Fähigkeit aus Prompt-Text. Nur Ende-zu-Ende geprüfte Einträge gelten als verfügbar."
    )
    return "\n".join(lines).strip()


def export_table() -> list[dict[str, str]]:
    rows = []
    for c in list_all():
        st = c.get("effective_status") or c.get("last_test_status") or "TEST_REQUIRED"
        rows.append(
            {
                "capability": c["capability_id"],
                "name": c["name"],
                "status": st,
                "evidence": (c.get("technical_cause") or "")[:200],
                "missing": _missing_hint(st, c),
                "approval": "ja" if c.get("approval_needed") or st == "APPROVAL_REQUIRED" else "nein",
                "next_step": _next_step(st, c),
            }
        )
    return rows


def _missing_hint(st: str, c: dict[str, Any]) -> str:
    if st == "AVAILABLE":
        return "—"
    if st == "APPROVAL_REQUIRED":
        return "Owner-Freigabe"
    if st == "DISABLED_BY_POLICY":
        return "Policy-Flag / bewusste Sperre"
    if st == "NOT_CONFIGURED":
        return "Connector/Env/Pfad fehlt"
    if st == "TOKEN_EXPIRED":
        return "Token erneuern"
    if st == "PERMISSION_DENIED":
        return "Rechte fehlen"
    if st == "CONNECTION_FAILED":
        return "Verbindung/Dienst"
    if st == "DEGRADED":
        return "Erneuter Probe nötig"
    return "E2E-Test ausstehend"


def _next_step(st: str, c: dict[str, Any]) -> str:
    if st == "AVAILABLE":
        return "Nur Read nutzen; Writes weiter freigabepflichtig prüfen"
    if st == "APPROVAL_REQUIRED":
        return "Freigabefluss + isolierter Test"
    if st == "DISABLED_BY_POLICY":
        return "Bewusst gesperrt lassen bis Auftrag"
    if st in ("NOT_CONFIGURED", "TEST_REQUIRED"):
        return f"Connector {c.get('connector')} verdrahten und Read-Probe"
    if st == "TOKEN_EXPIRED":
        return "Token rotieren, dann Read-Probe"
    if st == "DEGRADED":
        return "Capability-Scan erneut ausführen"
    return "Ursache beheben, Read-only neu prüfen"

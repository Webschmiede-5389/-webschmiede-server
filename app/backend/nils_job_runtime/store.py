# -*- coding: utf-8 -*-
"""SQLite job store for Nils persistent runtime."""
from __future__ import annotations

import hashlib
import logging
import os
import re
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nils_job_runtime.model import ACTIVE, TERMINAL, assert_transition, can_transition

log = logging.getLogger("nils_job_runtime.store")

_DEFAULT_DB = Path(
    os.getenv("NILS_RUNTIME_DB", "/var/lib/webschmiede/nils-runtime.db")
)
if os.name == "nt":
    _DEFAULT_DB = Path(__file__).resolve().parents[3] / "agency" / "nils-runtime.db"

_LOCK = threading.Lock()
_CODE_VERSION = os.getenv(
    "NILS_RUNTIME_CODE_VERSION", "2026-07-30-control-plane-1"
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS nils_jobs (
    job_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    telegram_chat_id TEXT,
    telegram_user_id TEXT,
    telegram_message_id TEXT,
    reply_to_message_id TEXT,
    task_type TEXT NOT NULL,
    task_summary TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    current_step TEXT,
    progress_current INTEGER NOT NULL DEFAULT 0,
    progress_total INTEGER NOT NULL DEFAULT 0,
    progress_message TEXT,
    created_at TEXT NOT NULL,
    queued_at TEXT,
    started_at TEXT,
    last_heartbeat_at TEXT,
    lease_expires_at TEXT,
    finished_at TEXT,
    next_attempt_at TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 2,
    timeout_seconds INTEGER NOT NULL DEFAULT 900,
    error_category TEXT,
    error_message_redacted TEXT,
    result_reference TEXT,
    worker_id TEXT,
    code_version TEXT,
    updated_at TEXT NOT NULL,
    shadow INTEGER NOT NULL DEFAULT 1,
    notify_last_progress_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_nils_jobs_status ON nils_jobs(status);
CREATE INDEX IF NOT EXISTS idx_nils_jobs_chat ON nils_jobs(telegram_chat_id);
CREATE INDEX IF NOT EXISTS idx_nils_jobs_lease ON nils_jobs(lease_expires_at);
CREATE INDEX IF NOT EXISTS idx_nils_jobs_queue ON nils_jobs(status, next_attempt_at, queued_at);

CREATE TABLE IF NOT EXISTS nils_job_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL
);
"""


def db_path() -> Path:
    return Path(os.getenv("NILS_RUNTIME_DB", str(_DEFAULT_DB)))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact(text: str | None, n: int = 400) -> str:
    t = (text or "").strip()
    t = re.sub(
        r"(?i)(password|secret|token|api[_-]?key|authorization)\s*[:=]\s*\S+",
        r"\1=***",
        t,
    )
    t = re.sub(r"\d{8,}:[A-Za-z0-9_-]{20,}", "BOT_TOKEN***", t)
    return t[:n]


def connect(path: Path | None = None) -> sqlite3.Connection:
    p = path or db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p), timeout=30, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA busy_timeout=5000")
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA temp_store=MEMORY")
    return con


def ensure_schema(con: sqlite3.Connection | None = None) -> Path:
    own = con is None
    c = con or connect()
    try:
        c.executescript(SCHEMA)
        # additive columns for external/cursor honesty
        cols = {r[1] for r in c.execute("PRAGMA table_info(nils_jobs)")}
        alter = {
            "external_kind": "TEXT",
            "external_ref": "TEXT",
            "external_pid": "INTEGER",
            "external_pgid": "INTEGER",
            "external_started_at": "TEXT",
            "external_last_step": "TEXT",
            "external_exit_code": "INTEGER",
            "external_finished_at": "TEXT",
            "result_validation": "TEXT",
            "workspace_path": "TEXT",
            "git_branch": "TEXT",
            "attempt_id": "TEXT",
            "parent_job_id": "TEXT",
            "job_class": "TEXT",
            # control-plane fields
            "kunde": "TEXT",
            "projekt": "TEXT",
            "capability": "TEXT",
            "target_system": "TEXT",
            "expected_result": "TEXT",
            "pipeline_stage": "TEXT",
            "original_request": "TEXT",
            "approval_required": "TEXT",
            "preflight_result": "TEXT",
            "last_status_notified": "TEXT",
            "turn_context": "TEXT",
        }
        for col, typ in alter.items():
            if col not in cols:
                c.execute(f"ALTER TABLE nils_jobs ADD COLUMN {col} {typ}")
        c.commit()
    finally:
        if own:
            c.close()
    return db_path()


def sqlite_health(path: Path | None = None) -> dict[str, Any]:
    """Read-only-ish health probe (opens DB briefly)."""
    p = path or db_path()
    out: dict[str, Any] = {"path": str(p), "exists": p.exists()}
    if not p.exists():
        return out
    st = p.stat()
    out["size"] = st.st_size
    out["mode"] = oct(st.st_mode & 0o777)
    out["uid"] = st.st_uid
    out["gid"] = st.st_gid
    con = connect(p)
    try:
        out["journal_mode"] = con.execute("PRAGMA journal_mode").fetchone()[0]
        out["synchronous"] = con.execute("PRAGMA synchronous").fetchone()[0]
        out["busy_timeout"] = con.execute("PRAGMA busy_timeout").fetchone()[0]
        out["foreign_keys"] = con.execute("PRAGMA foreign_keys").fetchone()[0]
        out["integrity_check"] = con.execute("PRAGMA integrity_check").fetchone()[0]
        out["job_count"] = con.execute("SELECT COUNT(*) FROM nils_jobs").fetchone()[0]
        out["running"] = con.execute(
            "SELECT COUNT(*) FROM nils_jobs WHERE status='RUNNING'"
        ).fetchone()[0]
        out["queued"] = con.execute(
            "SELECT COUNT(*) FROM nils_jobs WHERE status='QUEUED'"
        ).fetchone()[0]
    finally:
        con.close()
    return out


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def make_job_id(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    day = now.strftime("%Y%m%d")
    # sequential-ish via time + short uuid
    seq = now.strftime("%H%M%S")
    return f"NILS-{day}-{seq}-{uuid.uuid4().hex[:4]}"


def idempotency_key(
    *,
    bot_id: str,
    chat_id: str,
    message_id: str | int,
    task_type: str,
) -> str:
    raw = f"{bot_id}|{chat_id}|{message_id}|{task_type}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_job(
    *,
    task_type: str,
    task_summary: str,
    telegram_chat_id: str | None = None,
    telegram_user_id: str | None = None,
    telegram_message_id: str | None = None,
    reply_to_message_id: str | None = None,
    idempotency_key_value: str | None = None,
    timeout_seconds: int = 900,
    max_retries: int = 2,
    shadow: bool = True,
    bot_id: str = "nils",
) -> dict[str, Any]:
    ensure_schema()
    now = utc_now()
    ikey = idempotency_key_value or idempotency_key(
        bot_id=bot_id,
        chat_id=str(telegram_chat_id or "none"),
        message_id=str(telegram_message_id or uuid.uuid4().hex),
        task_type=task_type,
    )
    job_id = make_job_id()
    with _LOCK:
        con = connect()
        try:
            existing = con.execute(
                "SELECT * FROM nils_jobs WHERE idempotency_key=?", (ikey,)
            ).fetchone()
            if existing:
                return _row_to_dict(existing)  # type: ignore[return-value]
            con.execute(
                """
                INSERT INTO nils_jobs (
                    job_id, idempotency_key, telegram_chat_id, telegram_user_id,
                    telegram_message_id, reply_to_message_id, task_type, task_summary,
                    status, created_at, updated_at, timeout_seconds, max_retries,
                    code_version, shadow
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    job_id,
                    ikey,
                    str(telegram_chat_id) if telegram_chat_id else None,
                    str(telegram_user_id) if telegram_user_id else None,
                    str(telegram_message_id) if telegram_message_id is not None else None,
                    str(reply_to_message_id) if reply_to_message_id is not None else None,
                    task_type[:64],
                    redact(task_summary, 500),
                    "RECEIVED",
                    now,
                    now,
                    int(timeout_seconds),
                    int(max_retries),
                    _CODE_VERSION,
                    1 if shadow else 0,
                ),
            )
            _event(con, job_id, "created", "RECEIVED")
            con.commit()
            return get_job(job_id, con=con)  # type: ignore[return-value]
        finally:
            con.close()


def enqueue(job_id: str) -> dict[str, Any]:
    return transition(job_id, "QUEUED", extra={"queued_at": utc_now()})


def transition(
    job_id: str,
    to_status: str,
    *,
    extra: dict[str, Any] | None = None,
    con: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    own = con is None
    c = con or connect()
    try:
        row = c.execute("SELECT * FROM nils_jobs WHERE job_id=?", (job_id,)).fetchone()
        if not row:
            raise KeyError(f"job_not_found:{job_id}")
        cur = row["status"]
        if cur in TERMINAL and to_status != cur:
            if cur in ("SUCCEEDED", "COMPLETED"):
                raise ValueError("succeeded_job_not_rerunnable")
            assert_transition(cur, to_status)
        else:
            assert_transition(cur, to_status)
        fields = {"status": to_status, "updated_at": utc_now()}
        if extra:
            fields.update(extra)
        sets = ", ".join(f"{k}=?" for k in fields)
        c.execute(
            f"UPDATE nils_jobs SET {sets} WHERE job_id=?",
            (*fields.values(), job_id),
        )
        _event(c, job_id, "status", f"{cur}->{to_status}")
        if own:
            c.commit()
        return get_job(job_id, con=c)  # type: ignore[return-value]
    finally:
        if own:
            c.close()


def _event(con: sqlite3.Connection, job_id: str, event_type: str, detail: str = "") -> None:
    con.execute(
        "INSERT INTO nils_job_events (job_id, event_type, detail, created_at) VALUES (?,?,?,?)",
        (job_id, event_type, redact(detail, 300), utc_now()),
    )


def get_job(job_id: str, *, con: sqlite3.Connection | None = None) -> dict[str, Any] | None:
    own = con is None
    c = con or connect()
    try:
        return _row_to_dict(
            c.execute("SELECT * FROM nils_jobs WHERE job_id=?", (job_id,)).fetchone()
        )
    finally:
        if own:
            c.close()


def get_job_for_chat(job_id: str, chat_id: str) -> dict[str, Any] | None:
    job = get_job(job_id)
    if not job:
        return None
    if str(job.get("telegram_chat_id") or "") != str(chat_id):
        return None
    return job


def update_fields(job_id: str, **fields: Any) -> dict[str, Any]:
    if not fields:
        job = get_job(job_id)
        if not job:
            raise KeyError(job_id)
        return job
    fields = {k: v for k, v in fields.items() if k != "status"}
    fields["updated_at"] = utc_now()
    with _LOCK:
        con = connect()
        try:
            sets = ", ".join(f"{k}=?" for k in fields)
            con.execute(
                f"UPDATE nils_jobs SET {sets} WHERE job_id=?",
                (*fields.values(), job_id),
            )
            con.commit()
            return get_job(job_id, con=con)  # type: ignore[return-value]
        finally:
            con.close()


def queue_ahead_count(job_id: str) -> int:
    job = get_job(job_id)
    if not job or job["status"] != "QUEUED":
        return 0
    con = connect()
    try:
        q_at = job.get("queued_at") or job["created_at"]
        row = con.execute(
            """
            SELECT COUNT(*) FROM nils_jobs
            WHERE status='QUEUED' AND queued_at IS NOT NULL AND queued_at < ?
            """,
            (q_at,),
        ).fetchone()
        return int(row[0] if row else 0)
    finally:
        con.close()


def list_active_for_chat(chat_id: str, limit: int = 10) -> list[dict[str, Any]]:
    con = connect()
    try:
        active_list = sorted(ACTIVE)
        placeholders = ",".join("?" for _ in active_list)
        rows = con.execute(
            f"""
            SELECT * FROM nils_jobs
            WHERE telegram_chat_id=? AND status IN ({placeholders})
            ORDER BY created_at DESC LIMIT ?
            """,
            (str(chat_id), *active_list, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def get_single_active_for_chat(chat_id: str) -> dict[str, Any] | None:
    """At most one active execution job per chat (newest)."""
    jobs = list_active_for_chat(chat_id, limit=1)
    return jobs[0] if jobs else None


_CREATE_CAPS_BREAK_OFFER_CTX = frozenset(
    {
        "crm.prospect_create",
        "crm.customer_write",
        "crm.deal_open",
        "crm.offer_write",
        "crm.deal_close",
        "crm.note_create",
        "crm.inbound_accept",
    }
)
_OFFER_CAPS_FOR_BACKREF = frozenset(
    {
        "crm.offer_read",
        "crm.read",
        "crm.offer_pdf_send",
        "crm.customer_read",
    }
)


def get_last_crm_entity_for_chat(chat_id: str, *, limit: int = 20) -> dict[str, Any] | None:
    """Latest offer/read entity for explicit back-reference reuse only.

    A newer create/write CRM job (any non-terminal-cancel-before status) ends the
    prior offer context — „noch einmal“ must then ask, not silently reuse mbp.
    """
    import json

    con = connect()
    try:
        rows = con.execute(
            """
            SELECT job_id, capability, task_type, status, turn_context, result_reference,
                   original_request, finished_at, created_at
            FROM nils_jobs
            WHERE telegram_chat_id=?
              AND (
                capability LIKE 'crm.%'
                OR task_type LIKE 'crm.%'
              )
            ORDER BY COALESCE(finished_at, updated_at, created_at) DESC
            LIMIT ?
            """,
            (str(chat_id), int(limit)),
        ).fetchall()
    finally:
        con.close()

    for row in rows:
        job = dict(row)
        cap = (job.get("capability") or job.get("task_type") or "").strip()
        status = (job.get("status") or "").strip()
        if status == "CANCELLED":
            # Cancelled create still counts as intentional context break if it was started
            if cap in _CREATE_CAPS_BREAK_OFFER_CTX:
                return None
            continue
        if cap in _CREATE_CAPS_BREAK_OFFER_CTX:
            return None  # offer context intentionally ended
        if status not in ("SUCCEEDED", "COMPLETED"):
            continue
        if cap not in _OFFER_CAPS_FOR_BACKREF:
            continue
        company = ""
        raw = job.get("turn_context")
        if raw:
            try:
                data = json.loads(raw) if isinstance(raw, str) else raw
            except (json.JSONDecodeError, TypeError):
                data = None
            if isinstance(data, dict):
                collected = data.get("collected_parameters") or {}
                company = (
                    (collected.get("company") or collected.get("customer") or "")
                    .strip()
                )
        if not company:
            continue
        return {
            "job_id": job.get("job_id"),
            "company": company[:120],
            "capability": cap,
            "status": status,
        }
    return None


def mark_recovery_required(job_id: str, reason: str) -> dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise KeyError(job_id)
    if job["status"] in TERMINAL:
        return job
    if job["status"] == "RECOVERY_REQUIRED":
        return update_fields(
            job_id,
            error_category="recovery",
            error_message_redacted=redact(reason, 200),
            progress_message="RECOVERY_REQUIRED",
        )
    return transition(
        job_id,
        "RECOVERY_REQUIRED",
        extra={
            "error_category": "recovery",
            "error_message_redacted": redact(reason, 200),
            "progress_message": "RECOVERY_REQUIRED — keine stille Wiederholung",
            "worker_id": None,
            "lease_expires_at": None,
        },
    )

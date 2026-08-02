# -*- coding: utf-8 -*-
"""Lease-based durable queue on SQLite (no Redis required)."""
from __future__ import annotations

import logging
import os
import re
import socket
import time
from typing import Any

from nils_job_runtime import store
from nils_job_runtime.model import can_transition

log = logging.getLogger("nils_job_runtime.queue")

LEASE_SECONDS = int(os.getenv("NILS_JOB_LEASE_SECONDS", "90") or 90)
HEARTBEAT_SECONDS = int(os.getenv("NILS_JOB_HEARTBEAT_SECONDS", "30") or 30)
STALL_GRACE_SECONDS = int(os.getenv("NILS_JOB_STALL_GRACE_SECONDS", "120") or 120)


def worker_id() -> str:
    return os.getenv("NILS_WORKER_ID") or f"{socket.gethostname()}:{os.getpid()}"


def claim_next(
    *,
    wid: str | None = None,
    shadow_only: bool | None = None,
    live_capabilities: set[str] | list[str] | None = None,
) -> dict[str, Any] | None:
    """Atomically claim oldest QUEUED job whose next_attempt_at is due.

    Allowlist mode: with shadow_only=True and live_capabilities set, claim
    shadow=1 OR (shadow=0 AND capability in live_capabilities).
    """
    store.ensure_schema()
    wid = wid or worker_id()
    now = store.utc_now()
    now_ts = time.time()
    lease_exp = _iso_from_ts(now_ts + LEASE_SECONDS)
    live = {str(x).strip() for x in (live_capabilities or []) if str(x).strip()}
    if not live:
        raw = os.getenv("NILS_WORKER_LIVE_CAPABILITIES") or ""
        live = {p.strip() for p in re.split(r"[,;\s]+", raw) if p.strip()}
    with store._LOCK:
        con = store.connect()
        try:
            where_shadow = ""
            params: list[Any] = [now]
            if live and shadow_only is True:
                placeholders = ",".join("?" for _ in live)
                where_shadow = f" AND (shadow=1 OR (shadow=0 AND capability IN ({placeholders})))"
                params.extend(sorted(live))
            elif shadow_only is True:
                where_shadow = " AND shadow=1"
            elif shadow_only is False:
                where_shadow = " AND shadow=0"
            row = con.execute(
                f"""
                SELECT job_id FROM nils_jobs
                WHERE status='QUEUED'
                  AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
                  {where_shadow}
                ORDER BY queued_at ASC, created_at ASC
                LIMIT 1
                """,
                params,
            ).fetchone()
            if not row:
                return None
            job_id = row["job_id"]
            cur = con.execute(
                "SELECT status FROM nils_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            if not cur or cur["status"] != "QUEUED":
                return None
            if not can_transition("QUEUED", "RUNNING"):
                return None
            con.execute(
                """
                UPDATE nils_jobs SET
                    status='RUNNING',
                    worker_id=?,
                    started_at=COALESCE(started_at, ?),
                    last_heartbeat_at=?,
                    lease_expires_at=?,
                    updated_at=?,
                    current_step=COALESCE(current_step, 'started')
                WHERE job_id=? AND status='QUEUED'
                """,
                (wid, now, now, lease_exp, now, job_id),
            )
            if con.total_changes != 1:
                con.rollback()
                return None
            store._event(con, job_id, "claimed", wid)
            con.commit()
            return store.get_job(job_id, con=con)
        finally:
            con.close()


def heartbeat(
    job_id: str,
    *,
    wid: str | None = None,
    current_step: str | None = None,
    progress_current: int | None = None,
    progress_total: int | None = None,
    progress_message: str | None = None,
) -> dict[str, Any] | None:
    wid = wid or worker_id()
    now_ts = time.time()
    now = store.utc_now()
    lease_exp = _iso_from_ts(now_ts + LEASE_SECONDS)
    fields: dict[str, Any] = {
        "last_heartbeat_at": now,
        "lease_expires_at": lease_exp,
        "updated_at": now,
    }
    if current_step is not None:
        fields["current_step"] = store.redact(current_step, 200)
    if progress_current is not None:
        fields["progress_current"] = int(progress_current)
    if progress_total is not None:
        fields["progress_total"] = int(progress_total)
    if progress_message is not None:
        fields["progress_message"] = store.redact(progress_message, 300)
    with store._LOCK:
        con = store.connect()
        try:
            row = con.execute(
                "SELECT status, worker_id FROM nils_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            if not row or row["status"] != "RUNNING":
                return None
            if row["worker_id"] and row["worker_id"] != wid:
                return None
            sets = ", ".join(f"{k}=?" for k in fields)
            con.execute(
                f"UPDATE nils_jobs SET {sets} WHERE job_id=? AND worker_id=?",
                (*fields.values(), job_id, wid),
            )
            con.commit()
            return store.get_job(job_id, con=con)
        finally:
            con.close()


def release_for_worker_restart(job_id: str) -> dict[str, Any] | None:
    """Cooperative shutdown: RUNNING → STALLED → QUEUED so the next worker can resume.

    Does not mark FAILED. Avoids waiting for lease expiry after SIGTERM.
    """
    store.ensure_schema()
    now = store.utc_now()
    with store._LOCK:
        con = store.connect()
        try:
            row = con.execute(
                "SELECT * FROM nils_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            if not row or row["status"] != "RUNNING":
                return None
            retries = int(row["retry_count"] or 0)
            con.execute(
                """
                UPDATE nils_jobs SET status='STALLED', updated_at=?,
                    error_category='worker_restart',
                    error_message_redacted=?,
                    retry_count=?,
                    worker_id=NULL, lease_expires_at=NULL,
                    next_attempt_at=?
                WHERE job_id=? AND status='RUNNING'
                """,
                (
                    now,
                    "worker cooperative shutdown — requeue",
                    retries + 1,
                    now,
                    job_id,
                ),
            )
            con.execute(
                """
                UPDATE nils_jobs SET status='QUEUED', queued_at=?, updated_at=?
                WHERE job_id=? AND status='STALLED'
                """,
                (now, now, job_id),
            )
            store._event(con, job_id, "worker_restart_requeue", f"retry={retries+1}")
            con.commit()
            return store.get_job(job_id, con=con)
        finally:
            con.close()


def recover_stale_leases(*, wid: str | None = None) -> list[dict[str, Any]]:
    """Mark expired RUNNING leases as STALLED; requeue if retries remain."""
    store.ensure_schema()
    now = store.utc_now()
    now_ts = time.time()
    actions: list[dict[str, Any]] = []
    with store._LOCK:
        con = store.connect()
        try:
            rows = con.execute(
                """
                SELECT * FROM nils_jobs
                WHERE status='RUNNING'
                  AND lease_expires_at IS NOT NULL
                  AND lease_expires_at < ?
                """,
                (now,),
            ).fetchall()
            for row in rows:
                job = dict(row)
                job_id = job["job_id"]
                # also timeout by started_at + timeout_seconds
                started = _parse_ts(job.get("started_at")) or _parse_ts(job.get("created_at"))
                timed_out = False
                if started is not None:
                    if now_ts - started > int(job.get("timeout_seconds") or 900):
                        timed_out = True
                if timed_out:
                    con.execute(
                        """
                        UPDATE nils_jobs SET status='TIMED_OUT', finished_at=?, updated_at=?,
                            error_category='timeout', error_message_redacted=?,
                            worker_id=NULL, lease_expires_at=NULL
                        WHERE job_id=? AND status='RUNNING'
                        """,
                        (now, now, "max runtime exceeded", job_id),
                    )
                    store._event(con, job_id, "timeout", "lease_or_max_runtime")
                    actions.append({"job_id": job_id, "action": "TIMED_OUT"})
                    continue
                retries = int(job.get("retry_count") or 0)
                max_r = int(job.get("max_retries") or 2)
                # Cursor local: never auto-requeue (double-start risk)
                if (job.get("external_kind") or "") == "cursor_local":
                    con.execute(
                        """
                        UPDATE nils_jobs SET status='STALLED', finished_at=?, updated_at=?,
                            error_category='stalled', error_message_redacted=?,
                            worker_id=NULL, lease_expires_at=NULL
                        WHERE job_id=? AND status='RUNNING'
                        """,
                        (now, now, "cursor_lease_expired_no_autostart", job_id),
                    )
                    store._event(con, job_id, "stalled_final", "cursor_no_requeue")
                    actions.append({"job_id": job_id, "action": "STALLED"})
                    continue
                if retries < max_r:
                    next_at = _iso_from_ts(now_ts + min(60 * (2**retries), 600))
                    con.execute(
                        """
                        UPDATE nils_jobs SET status='STALLED', updated_at=?,
                            error_category='stalled', error_message_redacted=?,
                            retry_count=?, next_attempt_at=?,
                            worker_id=NULL, lease_expires_at=NULL
                        WHERE job_id=? AND status='RUNNING'
                        """,
                        (
                            now,
                            "heartbeat/lease expired",
                            retries + 1,
                            next_at,
                            job_id,
                        ),
                    )
                    # requeue after marking stalled
                    con.execute(
                        """
                        UPDATE nils_jobs SET status='QUEUED', queued_at=?, updated_at=?
                        WHERE job_id=? AND status='STALLED'
                        """,
                        (now, now, job_id),
                    )
                    store._event(con, job_id, "stalled_requeue", f"retry={retries+1}")
                    actions.append({"job_id": job_id, "action": "STALLED_REQUEUE"})
                else:
                    con.execute(
                        """
                        UPDATE nils_jobs SET status='STALLED', finished_at=?, updated_at=?,
                            error_category='stalled', error_message_redacted=?,
                            worker_id=NULL, lease_expires_at=NULL
                        WHERE job_id=? AND status='RUNNING'
                        """,
                        (now, now, "stalled max retries exceeded", job_id),
                    )
                    store._event(con, job_id, "stalled_final", "")
                    actions.append({"job_id": job_id, "action": "STALLED"})
            con.commit()
        finally:
            con.close()
    return actions


def _iso_from_ts(ts: float) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _parse_ts(value: str | None) -> float | None:
    if not value:
        return None
    try:
        from datetime import datetime

        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None

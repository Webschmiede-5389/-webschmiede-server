# -*- coding: utf-8 -*-
"""Observation-phase helpers: job protocol rows + daily ops check (metadata only)."""
from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from nils_job_runtime import queue, store
from nils_job_runtime import cursor_proc

log = logging.getLogger("nils_job_runtime.observation")

FREEZE_ID = "nils-owner-observation-2026-07-30"
CODE_VERSION = "2026-07-30-owner-observation-1"

OBSERVATION_ROOT = Path(
    os.getenv("NILS_OBSERVATION_DIR", "/var/lib/webschmiede/nils-observation")
)


def observation_enabled() -> bool:
    return (os.getenv("NILS_OBSERVATION_PHASE", "1") or "1").lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def ensure_dirs() -> Path:
    OBSERVATION_ROOT.mkdir(parents=True, exist_ok=True)
    (OBSERVATION_ROOT / "daily").mkdir(exist_ok=True)
    (OBSERVATION_ROOT / "jobs").mkdir(exist_ok=True)
    return OBSERVATION_ROOT


def _parse_ts(value: str | None) -> float | None:
    return queue._parse_ts(value)


def _runtime_seconds(job: dict[str, Any]) -> float | None:
    start = _parse_ts(job.get("started_at") or job.get("external_started_at"))
    end = _parse_ts(job.get("finished_at") or job.get("external_finished_at"))
    if start is None:
        return None
    if end is None:
        end = time.time()
    return max(0.0, end - start)


def _heartbeat_count(job_id: str) -> int:
    """Count heartbeat-like events from nils_job_events (best effort)."""
    con = store.connect()
    try:
        row = con.execute(
            """
            SELECT COUNT(*) FROM nils_job_events
            WHERE job_id=? AND (
                event_type LIKE '%heartbeat%'
                OR event_type='status'
                OR detail LIKE '%heartbeat%'
            )
            """,
            (job_id,),
        ).fetchone()
        # Prefer progress updates in last_heartbeat presence as 1 if running history thin
        n = int(row[0] if row else 0)
        return n
    finally:
        con.close()


def job_protocol_row(job: dict[str, Any]) -> dict[str, Any]:
    """Technical metadata only — no Telegram bodies, no secrets."""
    jid = job["job_id"]
    validation = (job.get("result_validation") or "").strip().lower()
    val_pass = validation in ("validated", "ok", "pass")
    if job.get("status") == "SUCCEEDED" and not val_pass and not validation:
        # SUCCEEDED without stored validation string → treat as fail for observation honesty
        val_pass = False
        validation_flag = "FAIL"
    elif job.get("status") == "SUCCEEDED" and val_pass:
        validation_flag = "PASS"
    elif job.get("status") == "RESULT_VALIDATION_FAILED":
        validation_flag = "FAIL"
    elif validation:
        validation_flag = "PASS" if val_pass else "FAIL"
    else:
        validation_flag = "n/a"

    cancel_req = job.get("status") in ("CANCEL_REQUESTED", "CANCELLED") or (
        "cancel" in (job.get("external_last_step") or "").lower()
    )
    pid = int(job.get("external_pid") or 0)
    orphans = 0
    if pid and job.get("status") in (
        "SUCCEEDED",
        "FAILED",
        "TIMED_OUT",
        "CANCELLED",
        "RESULT_VALIDATION_FAILED",
        "STALLED",
    ):
        if cursor_proc.pid_alive(pid):
            orphans = 1 + len(cursor_proc.list_children(pid))

    notify_ok = "n/a"
    # Infer from absence of notify failure events
    con = store.connect()
    try:
        fail_n = con.execute(
            "SELECT COUNT(*) FROM nils_job_events WHERE job_id=? AND event_type LIKE '%notify%fail%'",
            (jid,),
        ).fetchone()[0]
        if job.get("status") in (
            "SUCCEEDED",
            "FAILED",
            "TIMED_OUT",
            "CANCELLED",
            "RESULT_VALIDATION_FAILED",
        ):
            notify_ok = "FAIL" if int(fail_n or 0) > 0 else "PASS"
    finally:
        con.close()

    alarm = "nein"
    if job.get("status") in ("STALLED", "TIMED_OUT", "RESULT_VALIDATION_FAILED") or orphans:
        alarm = "ja"

    manual = "nein"
    if job.get("status") == "STALLED" or (
        job.get("error_category") or ""
    ).startswith("worker_restart"):
        manual = "ja"

    return {
        "job_id": jid,
        "attempt_id": job.get("attempt_id"),
        "task_type": job.get("task_type"),
        "job_class": job.get("job_class"),
        "repository": job.get("workspace_path"),
        "branch": job.get("git_branch"),
        "created_at": job.get("created_at"),
        "started_at": job.get("started_at") or job.get("external_started_at"),
        "finished_at": job.get("finished_at") or job.get("external_finished_at"),
        "final_status": job.get("status"),
        "runtime_seconds": _runtime_seconds(job),
        "heartbeat_events": _heartbeat_count(jid),
        "retry_count": int(job.get("retry_count") or 0),
        "parent_job_id": job.get("parent_job_id"),
        "cancel_requested": "ja" if cancel_req else "nein",
        "result_validation": validation_flag,
        "telegram_completion": notify_ok,
        "ops_alarm": alarm,
        "orphan_processes": orphans,
        "manual_intervention": manual,
        "freeze_id": FREEZE_ID,
        "code_version": job.get("code_version") or CODE_VERSION,
    }


def observation_started_at() -> str | None:
    p = OBSERVATION_ROOT / "STARTED_AT"
    if not p.is_file():
        return None
    try:
        return p.read_text(encoding="utf-8").strip() or None
    except Exception:
        return None


def export_owner_job_protocols(*, since_iso: str | None = None) -> dict[str, Any]:
    """Write/overwrite per-job JSON protocol files for owner_job (+ cursor canary owner)."""
    ensure_dirs()
    if since_iso is None:
        since_iso = observation_started_at()
    con = store.connect()
    try:
        if since_iso:
            rows = con.execute(
                """
                SELECT * FROM nils_jobs
                WHERE task_type IN ('owner_job','cursor_canary')
                  AND created_at >= ?
                ORDER BY created_at ASC
                """,
                (since_iso,),
            ).fetchall()
        else:
            rows = con.execute(
                """
                SELECT * FROM nils_jobs
                WHERE task_type IN ('owner_job','cursor_canary')
                ORDER BY created_at ASC
                """
            ).fetchall()
    finally:
        con.close()

    written = []
    for row in rows:
        job = dict(row)
        proto = job_protocol_row(job)
        path = OBSERVATION_ROOT / "jobs" / f"{job['job_id']}.json"
        path.write_text(json.dumps(proto, indent=2, ensure_ascii=False), encoding="utf-8")
        written.append(job["job_id"])
    index = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(written),
        "job_ids": written,
        "since_iso": since_iso,
        "scope": "observation_window" if since_iso else "all_owner_cursor",
    }
    (OBSERVATION_ROOT / "jobs_index.json").write_text(
        json.dumps(index, indent=2), encoding="utf-8"
    )
    return index


def daily_ops_check() -> dict[str, Any]:
    """Compact 24h ops dataset + hard-gate evaluation."""
    ensure_dirs()
    now = datetime.now(timezone.utc)
    day = now.strftime("%Y-%m-%d")
    since = (now - timedelta(hours=24)).isoformat()

    health = store.sqlite_health()
    worker = subprocess.getoutput("systemctl is-active nils-job-worker 2>/dev/null").strip()
    snack = subprocess.getoutput("systemctl is-active snack-api 2>/dev/null").strip()
    nrestarts = subprocess.getoutput(
        "systemctl show nils-job-worker -p NRestarts --value 2>/dev/null"
    ).strip()

    import shutil

    usage = shutil.disk_usage(str(store.db_path().parent))
    free_mb = usage.free // (1024 * 1024)

    con = store.connect()
    try:
        counts: dict[str, int] = {}
        for row in con.execute(
            "SELECT status, COUNT(*) FROM nils_jobs WHERE created_at LIKE ? GROUP BY status",
            (f"{day}%",),
        ):
            counts[row[0]] = int(row[1])

        oldest = con.execute(
            """
            SELECT job_id, status, created_at FROM nils_jobs
            WHERE status IN ('QUEUED','RUNNING','WAITING','STALLED','CANCEL_REQUESTED')
            ORDER BY created_at ASC LIMIT 1
            """
        ).fetchone()

        running_stale = []
        now_ts = time.time()
        for row in con.execute(
            "SELECT * FROM nils_jobs WHERE status='RUNNING'"
        ):
            job = dict(row)
            hb = _parse_ts(job.get("last_heartbeat_at"))
            if hb and now_ts - hb > 180:
                running_stale.append(job["job_id"])

        cancel_alive = []
        for row in con.execute(
            "SELECT * FROM nils_jobs WHERE status='CANCEL_REQUESTED'"
        ):
            job = dict(row)
            pid = int(job.get("external_pid") or 0)
            if pid and cursor_proc.pid_alive(pid):
                cancel_alive.append(f"{job['job_id']}:{pid}")

        # orphan runners
        orphans = 0
        proc = Path("/proc")
        if proc.is_dir():
            for p in proc.iterdir():
                if not p.name.isdigit():
                    continue
                try:
                    cmd = (p / "cmdline").read_bytes().replace(b"\x00", b" ").decode(
                        "utf-8", "replace"
                    )
                    if "cursor_local_runner.py" in cmd:
                        # check if belonging to non-terminal job
                        orphans += 1
                except Exception:
                    continue

        queue_len = con.execute(
            "SELECT COUNT(*) FROM nils_jobs WHERE status='QUEUED'"
        ).fetchone()[0]
    finally:
        con.close()

    # last backup marker
    bak_dir = Path(os.getenv("NILS_RUNTIME_BACKUP_DIR", "/root/app/backups/nils-runtime"))
    last_bak = None
    if bak_dir.is_dir():
        files = sorted(bak_dir.glob("nils-runtime-*.db"), key=lambda p: p.stat().st_mtime)
        if files:
            last_bak = {
                "file": files[-1].name,
                "mtime": datetime.fromtimestamp(
                    files[-1].stat().st_mtime, tz=timezone.utc
                ).isoformat(),
            }

    last_restore = None
    restore_marker = OBSERVATION_ROOT / "last_restore_test.json"
    if restore_marker.is_file():
        try:
            last_restore = json.loads(restore_marker.read_text(encoding="utf-8"))
        except Exception:
            last_restore = {"status": "unreadable"}

    started_at_path = OBSERVATION_ROOT / "STARTED_AT"
    phase_age_hours = 0.0
    if started_at_path.is_file():
        try:
            started = datetime.fromisoformat(started_at_path.read_text(encoding="utf-8").strip())
            phase_age_hours = (now - started).total_seconds() / 3600.0
        except Exception:
            phase_age_hours = 0.0

    # hard gates
    blocked_reasons: list[str] = []
    if health.get("integrity_check") not in (None, "ok"):
        blocked_reasons.append("sqlite_integrity")
    if worker != "active":
        blocked_reasons.append("worker_down")
    if cancel_alive:
        blocked_reasons.append("cancel_process_alive")
    if not last_bak:
        # Day-0: warn only. After >26h without backup → BLOCKED (hard gate).
        if phase_age_hours >= 26:
            blocked_reasons.append("backup_missing")
        else:
            blocked_reasons.append("backup_missing_warn")

    # false SUCCEEDED without validation (only within observation window)
    obs_since = observation_started_at() or since
    con = store.connect()
    try:
        false_ok = con.execute(
            """
            SELECT job_id FROM nils_jobs
            WHERE status='SUCCEEDED'
              AND task_type='owner_job'
              AND created_at >= ?
              AND (result_validation IS NULL OR result_validation NOT IN ('validated'))
            """,
            (obs_since,),
        ).fetchall()
    finally:
        con.close()
    if false_ok:
        blocked_reasons.append("false_succeeded_or_unvalidated")

    status = "OK"
    if any(
        r in blocked_reasons
        for r in (
            "sqlite_integrity",
            "worker_down",
            "cancel_process_alive",
            "false_succeeded_or_unvalidated",
            "backup_missing",
        )
    ):
        status = "BLOCKED"
    elif blocked_reasons:
        status = "WARN"

    report = {
        "day": day,
        "checked_at": now.isoformat(),
        "freeze_id": FREEZE_ID,
        "code_version": CODE_VERSION,
        "status": status,
        "blocked_reasons": blocked_reasons,
        "worker_active": worker,
        "worker_nrestarts": nrestarts,
        "snack_api_active": snack,
        "sqlite_integrity": health.get("integrity_check"),
        "queue_length": int(queue_len or 0),
        "oldest_open": dict(oldest) if oldest else None,
        "running_without_heartbeat": running_stale,
        "counts_today": counts,
        "cancel_processes_still_active": cancel_alive,
        "orphan_runner_processes": orphans,
        "disk_free_mb": free_mb,
        "last_backup": last_bak,
        "last_restore_test": last_restore,
        "alarm_channel": "ops_alert_local",
        "observation_phase": observation_enabled(),
        "phase_age_hours": round(phase_age_hours, 2),
    }

    out = OBSERVATION_ROOT / "daily" / f"{day}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    # append to ledger
    ledger = OBSERVATION_ROOT / "daily_ledger.jsonl"
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(report, ensure_ascii=False) + "\n")

    if status == "BLOCKED":
        try:
            from nils_job_runtime import notify

            notify._ops_alert(
                f"Nils OBSERVATION BLOCKED: {','.join(blocked_reasons)}"
            )
        except Exception:
            log.exception("observation alert")

    return report


def controlled_restore_test() -> dict[str, Any]:
    """
    Controlled SQLite restore drill: copy live DB → temp, integrity_check, row count.
    Does NOT replace the production database.
    """
    ensure_dirs()
    import shutil
    import sqlite3

    src = store.db_path()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest_dir = OBSERVATION_ROOT / "restore-tests"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"restore-copy-{stamp}.db"
    result: dict[str, Any] = {
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "source": str(src),
        "copy": str(dest),
        "status": "FAIL",
    }
    try:
        if not src.is_file():
            result["error"] = "source_missing"
            (OBSERVATION_ROOT / "last_restore_test.json").write_text(
                json.dumps(result, indent=2), encoding="utf-8"
            )
            return result
        # Prefer backup copy if available (safer than locking live under load)
        bak_dir = Path(os.getenv("NILS_RUNTIME_BACKUP_DIR", "/root/app/backups/nils-runtime"))
        bak_files = (
            sorted(bak_dir.glob("nils-runtime-*.db"), key=lambda p: p.stat().st_mtime)
            if bak_dir.is_dir()
            else []
        )
        copy_from = bak_files[-1] if bak_files else src
        result["copied_from"] = str(copy_from)
        shutil.copy2(copy_from, dest)
        # also copy WAL/SHM if present next to live source when copying live
        if copy_from == src:
            for suffix in ("-wal", "-shm"):
                side = Path(str(src) + suffix)
                if side.is_file():
                    shutil.copy2(side, Path(str(dest) + suffix))
        con = sqlite3.connect(str(dest))
        try:
            ick = con.execute("PRAGMA integrity_check").fetchone()[0]
            n = con.execute("SELECT COUNT(*) FROM nils_jobs").fetchone()[0]
            result["integrity_check"] = ick
            result["job_count"] = int(n)
            result["status"] = "PASS" if ick == "ok" else "FAIL"
        finally:
            con.close()
    except Exception as e:
        result["error"] = str(e)[:200]
        result["status"] = "FAIL"
        log.exception("controlled_restore_test")

    (OBSERVATION_ROOT / "last_restore_test.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def phase_counters(*, since_iso: str | None = None) -> dict[str, Any]:
    """Aggregate counters for observation report."""
    ensure_dirs()
    if since_iso is None:
        since_iso = observation_started_at()
    export_owner_job_protocols(since_iso=since_iso)
    jobs_dir = OBSERVATION_ROOT / "jobs"
    rows = []
    for p in sorted(jobs_dir.glob("NILS-*.json")):
        try:
            rows.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    if since_iso:
        rows = [r for r in rows if (r.get("created_at") or "") >= since_iso]

    def cnt(status: str) -> int:
        return sum(1 for r in rows if r.get("final_status") == status)

    runtimes = [float(r["runtime_seconds"]) for r in rows if r.get("runtime_seconds") is not None]
    long_jobs = sum(1 for r in runtimes if r >= 120.0)
    return {
        "freeze_id": FREEZE_ID,
        "code_version": CODE_VERSION,
        "jobs": len(rows),
        "SUCCEEDED": cnt("SUCCEEDED"),
        "FAILED": cnt("FAILED"),
        "TIMED_OUT": cnt("TIMED_OUT"),
        "STALLED": cnt("STALLED"),
        "CANCELLED": cnt("CANCELLED"),
        "RESULT_VALIDATION_FAILED": cnt("RESULT_VALIDATION_FAILED"),
        "retries": sum(1 for r in rows if r.get("parent_job_id") or int(r.get("retry_count") or 0) > 0),
        "cancels": sum(1 for r in rows if r.get("cancel_requested") == "ja"),
        "long_runtime_jobs_ge_120s": long_jobs,
        "lost_jobs": 0,  # filled manually / by gate if detected
        "double_processes": sum(1 for r in rows if int(r.get("orphan_processes") or 0) > 1),
        "false_success": sum(
            1
            for r in rows
            if r.get("final_status") == "SUCCEEDED" and r.get("result_validation") != "PASS"
        ),
        "manual_interventions": sum(1 for r in rows if r.get("manual_intervention") == "ja"),
        "avg_runtime_s": (sum(runtimes) / len(runtimes)) if runtimes else None,
        "max_runtime_s": max(runtimes) if runtimes else None,
    }

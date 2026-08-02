# -*- coding: utf-8 -*-
"""Monitoring probes for Nils job runtime → ops alert."""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from nils_job_runtime import queue, store

log = logging.getLogger("nils_job_runtime.monitor")

DISK_WARN_PCT = int(os.getenv("NILS_DISK_WARN_PCT", "90") or 90)
QUEUED_STALE_SECONDS = int(os.getenv("NILS_QUEUED_STALE_SECONDS", "3600") or 3600)
STALLED_ALERT_SECONDS = int(os.getenv("NILS_STALLED_ALERT_SECONDS", "900") or 900)


def _ops_alert(title: str, body: str) -> None:
    try:
        from nils_job_runtime import notify

        notify._ops_alert(f"{title}: {body}")
    except Exception:
        log.exception("ops alert")


def check_all() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    health = store.sqlite_health()
    if health.get("integrity_check") not in (None, "ok"):
        findings.append({"code": "sqlite_integrity", "severity": "critical", "detail": health.get("integrity_check")})
        _ops_alert("Nils SQLite integrity", str(health.get("integrity_check")))

    # writable?
    p = store.db_path()
    if p.exists() and not os.access(p, os.W_OK):
        findings.append({"code": "db_not_writable", "severity": "critical", "detail": str(p)})
        _ops_alert("Nils DB not writable", str(p))

    # disk
    usage = shutil.disk_usage(str(p.parent if p.exists() else "/var/lib/webschmiede"))
    pct = int(usage.used * 100 / usage.total) if usage.total else 0
    if pct >= DISK_WARN_PCT:
        findings.append({"code": "disk_low", "severity": "high", "detail": f"{pct}%"})
        _ops_alert("Nils disk low", f"{pct}% used")

    # worker service
    active = subprocess.getoutput("systemctl is-active nils-job-worker 2>/dev/null").strip()
    if active and active != "active":
        findings.append({"code": "worker_down", "severity": "critical", "detail": active})
        _ops_alert("Nils worker down", active)

    # restart loop (NRestarts high recently — best effort)
    nrestarts = subprocess.getoutput(
        "systemctl show nils-job-worker -p NRestarts --value 2>/dev/null"
    ).strip()
    try:
        if int(nrestarts or "0") >= 5:
            findings.append({"code": "worker_restart_loop", "severity": "high", "detail": nrestarts})
            _ops_alert("Nils worker restarts", nrestarts)
    except ValueError:
        pass

    # stale queued / running without heartbeat
    now = time.time()
    con = store.connect()
    try:
        for row in con.execute(
            "SELECT job_id, status, queued_at, last_heartbeat_at, lease_expires_at, updated_at, finished_at, external_pid, error_category FROM nils_jobs WHERE status IN ('QUEUED','RUNNING','STALLED','TIMED_OUT','CANCEL_REQUESTED','RESULT_VALIDATION_FAILED')"
        ):
            job = dict(row)
            if job["status"] == "QUEUED":
                q = queue._parse_ts(job.get("queued_at"))
                if q and now - q > QUEUED_STALE_SECONDS:
                    findings.append(
                        {
                            "code": "queued_stale",
                            "severity": "medium",
                            "detail": job["job_id"],
                        }
                    )
                    _ops_alert("Nils queue stale", job["job_id"])
            if job["status"] == "RUNNING":
                lease = queue._parse_ts(job.get("lease_expires_at"))
                hb = queue._parse_ts(job.get("last_heartbeat_at"))
                if (lease and lease < now) or (hb and now - hb > 180):
                    findings.append(
                        {
                            "code": "running_no_heartbeat",
                            "severity": "high",
                            "detail": job["job_id"],
                        }
                    )
            if job["status"] == "STALLED":
                findings.append({"code": "stalled_job", "severity": "high", "detail": job["job_id"]})
                u = queue._parse_ts(job.get("updated_at") or job.get("finished_at"))
                if u and now - u > STALLED_ALERT_SECONDS:
                    _ops_alert("Nils STALLED too long", job["job_id"])
            if job["status"] == "TIMED_OUT":
                findings.append({"code": "timed_out_job", "severity": "medium", "detail": job["job_id"]})
            if job["status"] == "CANCEL_REQUESTED":
                findings.append(
                    {"code": "cancel_requested", "severity": "high", "detail": job["job_id"]}
                )
                pid = int(job.get("external_pid") or 0)
                if pid:
                    try:
                        from nils_job_runtime import cursor_proc

                        if cursor_proc.pid_alive(pid):
                            findings.append(
                                {
                                    "code": "cancel_process_still_alive",
                                    "severity": "critical",
                                    "detail": f"{job['job_id']}:{pid}",
                                }
                            )
                            _ops_alert("Nils CANCEL process alive", f"{job['job_id']} pid={pid}")
                    except Exception:
                        pass
            if job["status"] == "RESULT_VALIDATION_FAILED":
                findings.append(
                    {
                        "code": "result_validation_failed",
                        "severity": "medium",
                        "detail": job["job_id"],
                    }
                )
    finally:
        con.close()

    # recover leases as part of monitor
    recovered = queue.recover_stale_leases()
    return {
        "ok": not any(f["severity"] == "critical" for f in findings),
        "findings": findings,
        "health": {k: health.get(k) for k in health if k != "path" or True},
        "disk_pct": pct,
        "worker_active": active,
        "recovered": recovered,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(check_all(), indent=2, default=str))

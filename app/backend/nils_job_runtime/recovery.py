# -*- coding: utf-8 -*-
"""Restart safety: load active jobs, mark unclear as RECOVERY_REQUIRED, no silent redo."""
from __future__ import annotations

import logging
from typing import Any

from nils_job_runtime import store
from nils_job_runtime.model import ACTIVE

log = logging.getLogger("nils_job_runtime.recovery")


def recover_after_restart(*, mark_running: bool = True) -> dict[str, Any]:
    """
    After bot/worker/server restart:
    - load active jobs
    - RUNNING/QUEUED with unclear lease → RECOVERY_REQUIRED (no auto write replay)
    - never silently re-execute write actions
    """
    store.ensure_schema()
    con = store.connect()
    recovered: list[str] = []
    informed: list[dict[str, Any]] = []
    try:
        rows = con.execute(
            f"""
            SELECT * FROM nils_jobs
            WHERE status IN ({",".join("?" for _ in sorted(ACTIVE))})
            """,
            tuple(sorted(ACTIVE)),
        ).fetchall()
        jobs = [dict(r) for r in rows]
    finally:
        con.close()

    for job in jobs:
        jid = job["job_id"]
        st = job["status"]
        # Unclear execution states must not auto-continue writes
        if st in ("RUNNING", "CANCEL_REQUESTED") and mark_running:
            try:
                nj = store.mark_recovery_required(
                    jid,
                    f"restart_recovery from {st}; no silent write replay",
                )
                recovered.append(jid)
                informed.append(
                    {
                        "job_id": jid,
                        "projekt": nj.get("projekt"),
                        "previous": st,
                        "status": nj.get("status"),
                    }
                )
            except Exception:
                log.exception("recovery_mark %s", jid)
        elif st == "QUEUED" and job.get("capability") in (
            "calendar.write",
            "email.send",
            "posting.publish",
            "n8n.execute",
        ):
            # Write-class queued jobs: hold for human review after restart
            try:
                nj = store.mark_recovery_required(
                    jid,
                    "restart_hold write-class QUEUED; no silent replay",
                )
                recovered.append(jid)
                informed.append(
                    {
                        "job_id": jid,
                        "projekt": nj.get("projekt"),
                        "previous": st,
                        "status": nj.get("status"),
                    }
                )
            except Exception:
                log.exception("recovery_queued %s", jid)

    return {
        "ok": True,
        "scanned": len(jobs),
        "recovered": recovered,
        "inform": informed,
        "text": _inform_text(informed),
    }


def _inform_text(informed: list[dict[str, Any]]) -> str:
    if not informed:
        return "Neustart: keine unklaren Jobs."
    lines = ["Nach Neustart unklare Jobs (RECOVERY_REQUIRED) — keine stille Wiederholung:"]
    for i in informed:
        lines.append(
            f"• {i['job_id']} ({i.get('projekt') or '–'}) "
            f"{i.get('previous')}→{i.get('status')}"
        )
    return "\n".join(lines)

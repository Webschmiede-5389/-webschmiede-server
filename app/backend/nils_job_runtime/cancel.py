# -*- coding: utf-8 -*-
"""Hardened cancel: CANCEL_REQUESTED → SIGTERM → grace → SIGKILL → CANCELLED."""
from __future__ import annotations

import logging
import time
from typing import Any

from nils_job_runtime import cursor_proc, notify, store
from nils_job_runtime import cursor_safety as safety
from nils_job_runtime import cursor_canary_tasks as tasks
from nils_job_runtime.model import CANCELLABLE, TERMINAL

log = logging.getLogger("nils_job_runtime.cancel")


def cancel_active_for_chat(chat_id: str) -> dict[str, Any]:
    """Cancel all active jobs for a chat (Stop). Idempotent."""
    active_list = store.list_active_for_chat(str(chat_id), limit=20)
    if not active_list:
        return {
            "ok": True,
            "already_terminal": True,
            "idempotent": True,
            "text": "Es läuft aktuell kein Auftrag.",
        }
    last: dict[str, Any] = {}
    for job in active_list:
        last = request_cancel(job["job_id"], chat_id=str(chat_id))
    # If any remain active, report failure
    still = store.list_active_for_chat(str(chat_id), limit=1)
    if still:
        return {
            "ok": False,
            "job": still[0],
            "text": f"Abbruch unvollständig — noch aktiv: {still[0]['job_id']}",
        }
    last = last or {}
    last["ok"] = True
    last["idempotent"] = len(active_list) == 0
    return last


def request_cancel(job_id: str, *, chat_id: str) -> dict[str, Any]:
    job = store.get_job_for_chat(job_id, str(chat_id))
    if not job:
        return {
            "ok": False,
            "text": f"Zugriff verweigert oder Auftrag nicht gefunden. Job-ID: {job_id}",
        }
    st = job["status"]
    if st in TERMINAL or st in (
        "SUCCEEDED",
        "FAILED",
        "TIMED_OUT",
        "TIMEOUT",
        "CANCELLED",
        "COMPLETED",
        "RESULT_VALIDATION_FAILED",
    ):
        return {
            "ok": True,
            "already_terminal": True,
            "idempotent": True,
            "text": f"Auftrag {job_id} ist bereits beendet ({st}).",
            "job": job,
        }

    if st not in CANCELLABLE and st != "CANCEL_REQUESTED":
        return {
            "ok": False,
            "text": f"Status {st} ist nicht abbrechbar.",
            "job": job,
        }

    # 1) CANCEL_REQUESTED — block follow-up actions; no new fachliche Aufgabe
    if st != "CANCEL_REQUESTED":
        try:
            job = store.transition(
                job_id,
                "CANCEL_REQUESTED",
                extra={
                    "current_step": "cancel_requested",
                    "pipeline_stage": "CANCEL",
                    "progress_message": "Abbruch angefordert — keine neuen Schritte",
                },
            )
        except Exception as e:
            log.exception("cancel_requested")
            return {"ok": False, "text": f"Cancel fehlgeschlagen: {store.redact(str(e), 80)}"}

    pid = int(job.get("external_pid") or 0)
    pgid = int(job.get("external_pgid") or 0) or None
    kill_info: dict[str, Any] = {}
    if pid:
        try:
            grace = float(safety.resource_limits()["grace_seconds"])
        except Exception:
            grace = 5.0
        kill_info = cursor_proc.kill_process_group(pgid, pid, grace_seconds=grace)
        time.sleep(0.5)
        still = cursor_proc.pid_alive(pid)
        if still:
            kill_info = cursor_proc.kill_process_group(pgid, pid, grace_seconds=grace)
            time.sleep(0.5)
            still = cursor_proc.pid_alive(pid)
        if still:
            try:
                notify._ops_alert(
                    f"CANCEL process still alive after grace job={job_id} pid={pid}"
                )
            except Exception:
                pass
            store.update_fields(
                job_id,
                error_category="cancel_process_alive",
                error_message_redacted=f"process_alive_after_cancel pid={pid}",
                external_last_step="cancel_process_still_alive",
            )
        else:
            store.update_fields(job_id, external_last_step="cancel_process_dead")

    repo_path = job.get("workspace_path") or ""
    post: dict[str, Any] = {}
    if repo_path:
        try:
            from pathlib import Path

            repo = Path(repo_path)
            if repo.is_dir():
                post["git_porcelain"] = tasks.git_status_porcelain(repo)[:800]
                post["git_diff"] = tasks.git_diff(repo)[:1500]
        except Exception:
            pass

    job = store.transition(
        job_id,
        "CANCELLED",
        extra={
            "finished_at": store.utc_now(),
            "worker_id": None,
            "lease_expires_at": None,
            "result_reference": store.redact(
                f"cancelled;kill={kill_info};post={post.get('git_porcelain','')[:120]}",
                300,
            ),
            "progress_message": "Abgebrochen",
            "pipeline_stage": "CANCELLED",
        },
    )
    try:
        notify.notify_status(job, "cancelled")
    except Exception:
        log.exception("notify_cancelled")
    return {
        "ok": True,
        "job": job,
        "kill": kill_info,
        "post_cancel": post,
        "idempotent": False,
        "text": (
            f"Auftrag {job_id} abgebrochen (CANCEL_REQUESTED→CANCELLED).\n"
            f"Prozessgruppe gestoppt. Job-ID: {job_id}"
        ),
    }

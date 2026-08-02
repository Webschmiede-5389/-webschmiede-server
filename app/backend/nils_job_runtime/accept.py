# -*- coding: utf-8 -*-
"""Accept Telegram tasks into persistent queue (shadow-safe)."""
from __future__ import annotations

import logging
import os
from typing import Any

from nils_job_runtime import notify, store

log = logging.getLogger("nils_job_runtime.accept")

SHADOW_MODE = (os.getenv("NILS_JOB_RUNTIME_MODE", "shadow") or "shadow").lower()


def accept_task(
    *,
    task_type: str,
    task_summary: str,
    chat_id: str,
    user_id: str | None = None,
    message_id: str | int | None = None,
    reply_to_message_id: str | int | None = None,
    timeout_seconds: int = 900,
    shadow: bool | None = None,
    notify_telegram: bool = True,
) -> dict[str, Any]:
    is_shadow = SHADOW_MODE != "live" if shadow is None else bool(shadow)
    job = store.create_job(
        task_type=task_type,
        task_summary=task_summary,
        telegram_chat_id=chat_id,
        telegram_user_id=user_id,
        telegram_message_id=message_id,
        reply_to_message_id=reply_to_message_id,
        timeout_seconds=timeout_seconds,
        shadow=is_shadow,
    )
    created_dup = job.get("status") != "RECEIVED"
    # If duplicate idempotent hit, job already exists (may be beyond RECEIVED)
    if job.get("status") == "RECEIVED":
        job = store.enqueue(job["job_id"])
        if notify_telegram:
            notify.notify_status(job, "accepted")
        return {
            "ok": True,
            "duplicate": False,
            "job": job,
            "text": (
                f"Auftrag {job['job_id']} wurde angenommen und in die Warteschlange gestellt."
            ),
        }
    return {
        "ok": True,
        "duplicate": True,
        "job": job,
        "text": (
            f"Auftrag {job['job_id']} war bereits erfasst (Idempotenz). "
            f"Status: {job.get('status')}."
        ),
    }

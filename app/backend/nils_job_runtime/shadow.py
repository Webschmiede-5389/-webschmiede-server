# -*- coding: utf-8 -*-
"""Shadow-mode Telegram commands — does not replace production Nils path."""
from __future__ import annotations

import logging
import os
import re
from typing import Any

log = logging.getLogger("nils_job_runtime.shadow")

SHADOW_ENABLED = (os.getenv("NILS_JOB_RUNTIME_SHADOW", "1") or "1").lower() not in (
    "0",
    "false",
    "no",
    "off",
)

# Commands (German + English)
_STATUS_RE = re.compile(
    r"(?i)^\s*(?:shadow\s*)?(?:jobstatus|job\s*status|status\s+job|"
    r"wie\s+weit(?:\s+bist\s+du)?|läuft\s+meine\s+aufgabe|was\s+macht\s+nils|"
    r"ist\s+der\s+auftrag\s+fertig)\b(?:\s+(?P<jid>NILS-[\w-]+))?\s*$"
)
_JOB_RE = re.compile(
    r"(?i)^\s*shadowjob\s+(?P<ttype>echo|steps|fail|block|heartbeat_long)"
    r"(?:\s+(?P<rest>.+))?\s*$"
)
_CANCEL_RE = re.compile(r"(?i)^\s*shadowcancel\s+(?P<jid>NILS-[\w-]+)\s*$")


def maybe_handle(
    *,
    text: str,
    chat_id: str,
    user_id: str | None = None,
    message_id: int | None = None,
) -> dict[str, Any] | None:
    """Return response dict if shadow command matched; else None."""
    if not SHADOW_ENABLED:
        return None
    t = (text or "").strip()
    if not t:
        return None

    m = _JOB_RE.match(t)
    if m:
        from nils_job_runtime.accept import accept_task

        ttype = m.group("ttype").lower()
        rest = (m.group("rest") or "").strip() or ttype
        timeout = 30 if ttype == "block" else 900
        if ttype == "heartbeat_long":
            timeout = 120
        res = accept_task(
            task_type=ttype,
            task_summary=rest[:400],
            chat_id=str(chat_id),
            user_id=user_id,
            message_id=message_id,
            timeout_seconds=timeout,
            shadow=True,
            notify_telegram=True,
        )
        return {"ok": True, "route": "shadow_accept", **res}

    m = _STATUS_RE.match(t)
    status_phrases = (
        "wie weit bist du",
        "wie weit",
        "läuft meine aufgabe noch",
        "was macht nils",
        "ist der auftrag fertig",
    )
    if m or t.lower() in status_phrases or t.lower().startswith("jobstatus"):
        from nils_job_runtime import store
        from nils_job_runtime.status_reply import answer_status_question

        jid = m.group("jid") if m else None
        explicit = bool(jid) or t.lower().startswith("jobstatus")
        has_active = bool(store.list_active_for_chat(str(chat_id), limit=1))
        if explicit or has_active or (jid is not None):
            text_out = answer_status_question(chat_id=str(chat_id), job_id=jid)
            return {
                "ok": True,
                "route": "shadow_status",
                "text": text_out,
            }
        return None

    m = _CANCEL_RE.match(t)
    if m:
        from nils_job_runtime import store
        from nils_job_runtime import notify

        jid = m.group("jid")
        job = store.get_job_for_chat(jid, str(chat_id))
        if not job:
            return {
                "ok": True,
                "route": "shadow_cancel",
                "text": "Zugriff verweigert oder Auftrag nicht gefunden.",
            }
        if job["status"] in ("SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLED"):
            return {
                "ok": True,
                "route": "shadow_cancel",
                "text": f"Auftrag {jid} ist bereits beendet ({job['status']}).",
            }
        job = store.transition(jid, "CANCELLED", extra={"finished_at": store.utc_now()})
        notify.notify_status(job, "cancelled")
        return {
            "ok": True,
            "route": "shadow_cancel",
            "text": f"Auftrag {jid} wurde abgebrochen.",
        }

    if t.lower() in ("shadow help", "shadowhilfe", "nils runtime help"):
        return {
            "ok": True,
            "route": "shadow_help",
            "text": (
                "Nils Job-Runtime (Shadow):\n"
                "• shadowjob echo|steps|fail|block|heartbeat_long [text]\n"
                "• jobstatus [NILS-…]\n"
                "• shadowcancel NILS-…\n"
                "Kein Minutenversprechen. Status nur aus der Job-Datenbank."
            ),
        }
    return None

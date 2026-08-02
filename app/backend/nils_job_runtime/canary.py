# -*- coding: utf-8 -*-
"""Canary routing: only authorized Telegram user → persistent runtime."""
from __future__ import annotations

import logging
import os
import re
from typing import Any

log = logging.getLogger("nils_job_runtime.canary")


def current_mode() -> str:
    return (os.getenv("NILS_JOB_RUNTIME_MODE", "shadow") or "shadow").lower().strip()


MODE = current_mode()

CANARY_TASK_TYPES = frozenset(
    {
        "echo",
        "steps",
        "fail",
        "block",
        "heartbeat_long",
        "external_proc",
        "cursor_probe",
        "cursor_canary",
    }
)

_CURSORCANARY_RE = re.compile(
    r"(?i)^\s*cursorcanary\s+"
    r"(?P<variant>readonly|writefile|branchedit|fail|timeout|long)"
    r"(?:\s+(?P<rest>.+))?\s*$"
)

_JOB_RE = re.compile(
    r"(?i)^\s*(?:canary|nilsjob|job)\s+"
    r"(?P<ttype>echo|steps|fail|block|heartbeat_long|external_proc|cursor_probe)"
    r"(?:\s+(?P<rest>.+))?\s*$"
)
_SHADOW_JOB_RE = re.compile(
    r"(?i)^\s*shadowjob\s+(?P<ttype>echo|steps|fail|block|heartbeat_long|external_proc|cursor_probe)"
    r"(?:\s+(?P<rest>.+))?\s*$"
)
_STATUS_RE = re.compile(
    r"(?i)^\s*(?:canary\s*)?(?:jobstatus|job\s*status|status\s+job)\s*(?P<jid>NILS-[\w-]+)?\s*$"
    r"|^\s*(?:wie\s+weit(?:\s+bist\s+du)?|läuft\s+meine\s+aufgabe(?:\s+noch)?|"
    r"was\s+macht\s+nils|ist\s+der\s+auftrag\s+fertig)"
    r"(?:\s+(?P<jid2>NILS-[\w-]+))?\s*$"
)
_CANCEL_RE = re.compile(
    r"(?i)^\s*(?:canarycancel|shadowcancel|jobcancel)\s+(?P<jid>NILS-[\w-]+)\s*$"
)


def canary_enabled() -> bool:
    return current_mode() in ("canary", "live")


def shadow_enabled() -> bool:
    return current_mode() in ("shadow", "canary") and (
        (os.getenv("NILS_JOB_RUNTIME_SHADOW", "1") or "1").lower()
        not in ("0", "false", "no", "off")
    )


def authorized_user_ids() -> list[str]:
    raw = (
        os.getenv("NILS_CANARY_TELEGRAM_USER_IDS")
        or os.getenv("TELEGRAM_OWNER_USER_ID")
        or os.getenv("TELEGRAM_OWNER_CHAT_ID")
        or os.getenv("TELEGRAM_OWNER_CHAT_IDS")
        or ""
    )
    parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
    return [p for p in parts if p.lstrip("-").isdigit()]


def is_canary_user(user_id: str | None, chat_id: str | None = None) -> bool:
    uid = str(user_id or "").strip()
    cid = str(chat_id or "").strip()
    allowed = set(authorized_user_ids())
    if not allowed:
        return False
    if uid and uid in allowed:
        return True
    if cid and cid in allowed:
        return True
    return False


def mask_id(value: str | None) -> str:
    v = str(value or "")
    if len(v) <= 4:
        return "****"
    return f"…{v[-4:]}"


def _accept_cursorcanary(
    *,
    variant: str,
    chat_id: str,
    user_id: str | None,
    message_id: int | None,
    mode: str,
) -> dict[str, Any]:
    from nils_job_runtime.accept import accept_task
    from nils_job_runtime import cursor_safety as safety

    if not safety.cursor_allowed():
        return {
            "ok": True,
            "route": "cursorcanary_disabled",
            "text": "Cursor-Canary ist deaktiviert (NILS_CANARY_ALLOW_CURSOR=0).",
        }
    if not is_canary_user(user_id, chat_id):
        return {
            "ok": True,
            "route": "canary_denied",
            "text": "Dieser Auftragspfad ist für deinen Account nicht freigeschaltet.",
        }
    # Reject dangerous free-form rest — only fixed variants
    if variant not in safety.ALLOWED_VARIANTS:
        return {
            "ok": True,
            "route": "cursorcanary_unsupported",
            "text": f"Unbekannte Cursor-Canary-Variante: {variant}",
        }
    timeouts = {
        "readonly": 600,
        "writefile": 600,
        "branchedit": 600,
        "fail": 300,
        "timeout": int(os.getenv("NILS_CANARY_TIMEOUT_TEST_SECONDS", "45") or 45),
        "long": 600,
    }
    # max_retries=0 via accept — patch after create by updating job
    res = accept_task(
        task_type="cursor_canary",
        task_summary=f"{variant} cursorcanary",
        chat_id=str(chat_id),
        user_id=str(user_id) if user_id else str(chat_id),
        message_id=message_id,
        timeout_seconds=timeouts.get(variant, 600),
        shadow=(mode == "shadow"),
        notify_telegram=True,
    )
    job = res.get("job") or {}
    # Force no auto-retry for cursor
    if job.get("job_id") and not res.get("duplicate"):
        from nils_job_runtime import store

        store.update_fields(job["job_id"], max_retries=0)
        job = store.get_job(job["job_id"]) or job
    text_out = res.get("text") or ""
    if job.get("job_id") and job["job_id"] not in text_out:
        text_out = f"{text_out}\nJob-ID: {job['job_id']}"
    text_out += f"\nCursor-Canary: {variant} (Allowlist-Repo, Local Agent)."
    return {
        "ok": True,
        "route": "cursorcanary_accept",
        "duplicate": res.get("duplicate"),
        "job": job,
        "text": text_out,
        "canary_user_masked": mask_id(user_id or chat_id),
    }


def maybe_handle(
    *,
    text: str,
    chat_id: str,
    user_id: str | None = None,
    message_id: int | None = None,
) -> dict[str, Any] | None:
    """Intercept canary/shadow/cursorcanary commands for authorized user only."""
    t = (text or "").strip()
    if not t:
        return None

    mode = current_mode()
    if mode == "off":
        return None

    m_status = _STATUS_RE.match(t)
    m_cancel = _CANCEL_RE.match(t)
    m_cursor = _CURSORCANARY_RE.match(t)
    m_job = _JOB_RE.match(t) or _SHADOW_JOB_RE.match(t)

    # Explicit cursorcanary only — never from free-form chat
    if m_cursor:
        if not is_canary_user(user_id, chat_id):
            return {
                "ok": True,
                "route": "canary_denied",
                "text": "Dieser Auftragspfad ist für deinen Account nicht freigeschaltet.",
            }
        return _accept_cursorcanary(
            variant=m_cursor.group("variant").lower(),
            chat_id=chat_id,
            user_id=user_id,
            message_id=message_id,
            mode=mode,
        )

    # Reject near-misses that look like cursor but lack explicit marker
    if re.match(r"(?i)^\s*cursor\s+", t) and not t.lower().startswith("cursor status"):
        if is_canary_user(user_id, chat_id):
            return {
                "ok": True,
                "route": "cursorcanary_hint",
                "text": (
                    "Cursor-Jobs nur explizit: "
                    "cursorcanary readonly|writefile|branchedit|fail|timeout|long"
                ),
            }
        return None

    wants_runtime = bool(
        m_job
        or m_status
        or m_cancel
        or t.lower()
        in (
            "canary help",
            "canaryhilfe",
            "nils runtime help",
            "shadow help",
            "shadowhilfe",
            "cursorcanary help",
        )
    )

    if not wants_runtime:
        from nils_job_runtime import store

        if t.lower() in (
            "wie weit bist du",
            "wie weit",
            "läuft meine aufgabe noch",
            "was macht nils",
            "ist der auftrag fertig",
        ) and store.list_active_for_chat(str(chat_id), limit=1):
            wants_runtime = True
        else:
            return None

    if not is_canary_user(user_id, chat_id):
        if m_job or (m_status and (m_status.group("jid") or m_status.group("jid2"))):
            return {
                "ok": True,
                "route": "canary_denied",
                "text": "Dieser Auftragspfad ist für deinen Account nicht freigeschaltet.",
            }
        return None

    if t.lower() in (
        "canary help",
        "canaryhilfe",
        "nils runtime help",
        "shadow help",
        "shadowhilfe",
        "cursorcanary help",
    ):
        return {
            "ok": True,
            "route": "canary_help",
            "text": (
                "Nils Job-Runtime (Canary):\n"
                "• canary echo|steps|fail|block|heartbeat_long|external_proc …\n"
                "• cursorcanary readonly|writefile|branchedit|fail|timeout|long\n"
                "• jobstatus NILS-…\n"
                "• canarycancel NILS-…\n"
                "Cursor nur mit cursorcanary + Allowlist. Keine Minutenversprechen."
            ),
        }

    if m_job:
        from nils_job_runtime.accept import accept_task

        ttype = m_job.group("ttype").lower()
        if ttype not in CANARY_TASK_TYPES:
            return {
                "ok": True,
                "route": "canary_unsupported",
                "text": f"Aufgabentyp '{ttype}' ist im Canary nicht freigegeben.",
            }
        rest = (m_job.group("rest") or "").strip() or ttype
        timeout = 30 if ttype == "block" else 900
        if ttype == "heartbeat_long":
            timeout = 180
        if ttype == "external_proc":
            timeout = 120
        if ttype == "cursor_probe":
            timeout = int(os.getenv("NILS_CANARY_CURSOR_TIMEOUT", "600") or 600)
        is_shadow = mode == "shadow"
        res = accept_task(
            task_type=ttype,
            task_summary=rest[:400],
            chat_id=str(chat_id),
            user_id=str(user_id) if user_id else str(chat_id),
            message_id=message_id,
            timeout_seconds=timeout,
            shadow=is_shadow,
            notify_telegram=True,
        )
        job = res.get("job") or {}
        text_out = res.get("text") or ""
        if job.get("job_id") and job["job_id"] not in text_out:
            text_out = f"{text_out}\nJob-ID: {job['job_id']}"
        return {
            "ok": True,
            "route": "canary_accept",
            "duplicate": res.get("duplicate"),
            "job": job,
            "text": text_out,
            "canary_user_masked": mask_id(user_id or chat_id),
        }

    if m_cancel:
        from nils_job_runtime.cancel import request_cancel

        r = request_cancel(m_cancel.group("jid"), chat_id=str(chat_id))
        return {
            "ok": True,
            "route": "canary_cancel",
            "text": r.get("text") or f"Auftrag {m_cancel.group('jid')} Abbruch.",
            "job": r.get("job"),
        }

    from nils_job_runtime import store
    from nils_job_runtime.status_reply import answer_status_question

    jid = None
    if m_status:
        jid = m_status.group("jid") or m_status.group("jid2")
    text_out = answer_status_question(chat_id=str(chat_id), job_id=jid)
    if jid and jid not in text_out:
        text_out = f"{text_out}\nJob-ID: {jid}"
    return {"ok": True, "route": "canary_status", "text": text_out}

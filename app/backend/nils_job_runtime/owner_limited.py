# -*- coding: utf-8 -*-
"""Owner-limited production routing: cursorjob / inspect / retry / jobs today."""
from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger("nils_job_runtime.owner_limited")

_CURSORJOB_RE = re.compile(
    r"(?i)^\s*cursorjob\s+"
    r"(?P<kind>readonly|branch|report|failtest)\s+"
    r"(?P<repo>[A-Za-z0-9._-]+)\s+"
    r"(?P<task>.+?)\s*$"
)
_JOBSTATUS_RE = re.compile(r"(?i)^\s*jobstatus\s+(?P<jid>NILS-[\w-]+)\s*$")
_JOBINSPECT_RE = re.compile(r"(?i)^\s*jobinspect\s+(?P<jid>NILS-[\w-]+)\s*$")
_JOBCANCEL_RE = re.compile(r"(?i)^\s*jobcancel\s+(?P<jid>NILS-[\w-]+)\s*$")
_JOBRETRY_RE = re.compile(r"(?i)^\s*jobretry\s+(?P<jid>NILS-[\w-]+)\s*$")
_JOBS_TODAY_RE = re.compile(r"(?i)^\s*jobs\s+today\s*$")


def owner_mode() -> str:
    return (os.getenv("NILS_OWNER_RUNTIME_MODE", "") or "").lower().strip()


def limited_enabled() -> bool:
    return owner_mode() == "limited"


def observation_freeze_active() -> bool:
    return (os.getenv("NILS_OBSERVATION_PHASE", "1") or "1").lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


ALLOWED_OBSERVATION_KINDS = frozenset({"readonly", "branch", "report", "failtest"})


def _owner_ids() -> list[str]:
    from nils_job_runtime.canary import authorized_user_ids

    return authorized_user_ids()


def is_owner(user_id: str | None, chat_id: str | None) -> bool:
    from nils_job_runtime.canary import is_canary_user

    return is_canary_user(user_id, chat_id)


def make_attempt_id() -> str:
    return f"ATT-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"


def _class_for_kind(kind: str) -> str:
    return {
        "readonly": "READ_ONLY_ANALYSIS",
        "branch": "BRANCH_CHANGE",
        "report": "REPORT_GENERATION",
        "failtest": "CONTROLLED_FAIL",
    }.get(kind.lower(), "")


def inspect_job(job_id: str, *, chat_id: str) -> str:
    from nils_job_runtime import store, cursor_proc
    from nils_job_runtime import cursor_canary_tasks as tasks
    from pathlib import Path

    job = store.get_job_for_chat(job_id, str(chat_id))
    if not job:
        return f"Zugriff verweigert oder Job nicht gefunden: {job_id}"

    pid = int(job.get("external_pid") or 0)
    alive = cursor_proc.pid_alive(pid) if pid else False
    repo = job.get("workspace_path") or ""
    diff = ""
    porcelain = ""
    if repo and Path(repo).is_dir():
        try:
            porcelain = tasks.git_status_porcelain(Path(repo))[:600]
            diff = tasks.git_diff(Path(repo))[:1200]
        except Exception:
            pass

    actions = []
    st = job.get("status")
    if st in ("FAILED", "TIMED_OUT", "STALLED", "RESULT_VALIDATION_FAILED"):
        actions.append(f"jobretry {job_id}")
    if st not in (
        "SUCCEEDED",
        "FAILED",
        "TIMED_OUT",
        "CANCELLED",
        "RESULT_VALIDATION_FAILED",
    ):
        actions.append(f"jobcancel {job_id}")
    actions.append(f"jobstatus {job_id}")

    lines = [
        f"Jobinspect {job_id}",
        f"Status: {st}",
        f"Typ/Klasse: {job.get('task_type')} / {job.get('job_class') or '–'}",
        f"Attempt: {job.get('attempt_id') or '–'}",
        f"Parent: {job.get('parent_job_id') or '–'}",
        f"Repo: {repo or '–'}",
        f"Branch: {job.get('git_branch') or '–'}",
        f"PID: {pid or '–'} (alive={alive})",
        f"PGID: {job.get('external_pgid') or '–'}",
        f"Heartbeat: {job.get('last_heartbeat_at') or '–'}",
        f"Letzter Schritt: {job.get('external_last_step') or job.get('current_step') or '–'}",
        f"Exit: {job.get('external_exit_code')}",
        f"Validierung: {job.get('result_validation') or '–'}",
        f"Ergebnisref: {job.get('result_reference') or '–'}",
        f"Fehler: {job.get('error_message_redacted') or '–'}",
        "",
        "Git porcelain:",
        porcelain or "(leer)",
        "",
        "Git diff (Auszug):",
        diff or "(leer)",
        "",
        "Sichere Aktionen:",
        *[f"• {a}" for a in actions],
    ]
    return "\n".join(lines)


def jobs_today_text() -> str:
    from nils_job_runtime import store

    store.ensure_schema()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    con = store.connect()
    try:
        counts = {
            s: 0
            for s in (
                "QUEUED",
                "RUNNING",
                "WAITING",
                "STALLED",
                "TIMED_OUT",
                "FAILED",
                "SUCCEEDED",
                "CANCELLED",
                "CANCEL_REQUESTED",
                "RESULT_VALIDATION_FAILED",
            )
        }
        for row in con.execute(
            "SELECT status, COUNT(*) FROM nils_jobs WHERE created_at LIKE ? GROUP BY status",
            (f"{today}%",),
        ):
            counts[row[0]] = int(row[1])

        def _one(sql: str) -> str:
            r = con.execute(sql).fetchone()
            if not r:
                return "–"
            return f"{r[0]} ({r[1]})"

        oldest_open = _one(
            """
            SELECT job_id, status FROM nils_jobs
            WHERE status IN ('QUEUED','RUNNING','WAITING','STALLED','CANCEL_REQUESTED')
            ORDER BY created_at ASC LIMIT 1
            """
        )
        last_ok = _one(
            """
            SELECT job_id, finished_at FROM nils_jobs
            WHERE status='SUCCEEDED' ORDER BY finished_at DESC LIMIT 1
            """
        )
        last_fail = _one(
            """
            SELECT job_id, finished_at FROM nils_jobs
            WHERE status IN ('FAILED','TIMED_OUT','RESULT_VALIDATION_FAILED','STALLED')
            ORDER BY COALESCE(finished_at, updated_at) DESC LIMIT 1
            """
        )
    finally:
        con.close()

    lines = ["Jobs today (SQLite):", *[f"• {k}: {v}" for k, v in counts.items() if True]]
    lines += [
        f"Ältester offener: {oldest_open}",
        f"Letzter Erfolg: {last_ok}",
        f"Letzter Fehler: {last_fail}",
    ]
    return "\n".join(lines)


def retry_job(job_id: str, *, chat_id: str, user_id: str | None) -> dict[str, Any]:
    from nils_job_runtime import store, accept, cursor_proc
    from nils_job_runtime import cursor_canary_tasks as tasks
    from pathlib import Path

    job = store.get_job_for_chat(job_id, str(chat_id))
    if not job:
        return {"ok": False, "text": f"Zugriff verweigert oder Job nicht gefunden: {job_id}"}
    st = job["status"]
    if st not in ("FAILED", "TIMED_OUT", "STALLED", "RESULT_VALIDATION_FAILED"):
        return {
            "ok": False,
            "text": f"Retry nur für FAILED/TIMED_OUT/STALLED/RESULT_VALIDATION_FAILED (ist {st}).",
        }
    if st == "SUCCEEDED" or (
        job.get("result_validation") == "validated" and st == "SUCCEEDED"
    ):
        return {"ok": False, "text": "Kein Retry bei bereits validiertem Erfolg."}

    pid = int(job.get("external_pid") or 0)
    if pid and cursor_proc.pid_alive(pid):
        return {
            "ok": False,
            "text": f"Prozess PID {pid} lebt noch — kein Retry (kein Doppelprozess). jobinspect {job_id}",
        }

    # Inspect existing diffs/files before retry
    repo = job.get("workspace_path") or ""
    note = ""
    if repo and Path(repo).is_dir():
        porc = tasks.git_status_porcelain(Path(repo))
        note = f"Vor Retry porcelain:\n{porc[:400] or '(clean)'}"

    attempt = make_attempt_id()
    summary = job.get("task_summary") or ""
    # Ensure attempt marker in summary for handler
    if "attempt=" not in summary:
        summary = f"{summary} | attempt={attempt}|parent={job_id}"
    else:
        summary = re.sub(r"attempt=[^\s|]+", f"attempt={attempt}", summary)
        if "parent=" not in summary:
            summary += f"|parent={job_id}"

    res = accept.accept_task(
        task_type=job.get("task_type") or "owner_job",
        task_summary=summary[:500],
        chat_id=str(chat_id),
        user_id=str(user_id or chat_id),
        message_id=f"retry-{attempt}",
        timeout_seconds=int(job.get("timeout_seconds") or 600),
        shadow=False,
        notify_telegram=True,
    )
    new_job = res.get("job") or {}
    njid = new_job.get("job_id")
    if njid:
        store.update_fields(
            njid,
            max_retries=0,
            attempt_id=attempt,
            parent_job_id=job_id,
            job_class=job.get("job_class"),
            workspace_path=job.get("workspace_path"),
            git_branch=job.get("git_branch"),
        )
        # event on old job
        con = store.connect()
        try:
            store._event(con, job_id, "retry_spawned", njid)
            con.commit()
        finally:
            con.close()
    return {
        "ok": True,
        "job": store.get_job(njid) if njid else new_job,
        "text": (
            f"Retry gestartet als neuer Attempt.\n"
            f"Alt: {job_id}\nNeu: {njid}\nAttempt: {attempt}\n"
            f"{note}\nJob-ID: {njid}"
        ),
    }


def maybe_handle(
    *,
    text: str,
    chat_id: str,
    user_id: str | None = None,
    message_id: int | None = None,
) -> dict[str, Any] | None:
    """Owner-limited explicit commands only. Never free-form agent start."""
    t = (text or "").strip()
    if not t:
        return None
    if not limited_enabled():
        # Still allow inspect/status for canary continuity? Only when limited.
        return None

    m_cj = _CURSORJOB_RE.match(t)
    m_st = _JOBSTATUS_RE.match(t)
    m_in = _JOBINSPECT_RE.match(t)
    m_ca = _JOBCANCEL_RE.match(t)
    m_re = _JOBRETRY_RE.match(t)
    m_td = _JOBS_TODAY_RE.match(t)

    if not any([m_cj, m_st, m_in, m_ca, m_re, m_td, t.lower() in ("cursorjob help", "owner help")]):
        # Near-miss: "cursorjob" without full form
        if re.match(r"(?i)^\s*cursorjob\b", t):
            if is_owner(user_id, chat_id):
                return {
                    "ok": True,
                    "route": "owner_hint",
                    "text": (
                        "Owner-Limited Syntax:\n"
                        "• cursorjob readonly <repo> <aufgabe>\n"
                        "• cursorjob branch <repo> <aufgabe>\n"
                        "• cursorjob report <repo> <aufgabe>\n"
                        "• jobstatus|jobinspect|jobcancel|jobretry <Job-ID>\n"
                        "• jobs today"
                    ),
                }
            return {
                "ok": True,
                "route": "owner_denied",
                "text": "Dieser Auftragspfad ist nicht freigeschaltet.",
            }
        return None

    if not is_owner(user_id, chat_id):
        return {
            "ok": True,
            "route": "owner_denied",
            "text": "Dieser Auftragspfad ist für deinen Account nicht freigeschaltet.",
        }

    if t.lower() in ("cursorjob help", "owner help"):
        return {
            "ok": True,
            "route": "owner_help",
            "text": (
                "Nils Owner-Limited Runtime:\n"
                "• cursorjob readonly|branch|report <repo> <aufgabe>\n"
                "• jobstatus / jobinspect / jobcancel / jobretry <Job-ID>\n"
                "• jobs today\n"
                "Kein freier Agent aus Normalchat. Kein Deploy/Push/main."
            ),
        }

    if m_td:
        return {"ok": True, "route": "jobs_today", "text": jobs_today_text()}

    if m_st:
        from nils_job_runtime.status_reply import answer_status_question

        jid = m_st.group("jid")
        txt = answer_status_question(chat_id=str(chat_id), job_id=jid)
        return {"ok": True, "route": "jobstatus", "text": f"{txt}\nJob-ID: {jid}"}

    if m_in:
        jid = m_in.group("jid")
        return {"ok": True, "route": "jobinspect", "text": inspect_job(jid, chat_id=str(chat_id))}

    if m_ca:
        from nils_job_runtime.cancel import request_cancel

        r = request_cancel(m_ca.group("jid"), chat_id=str(chat_id))
        return {"ok": True, "route": "jobcancel", "text": r.get("text") or "", "job": r.get("job")}

    if m_re:
        r = retry_job(m_re.group("jid"), chat_id=str(chat_id), user_id=user_id)
        return {"ok": bool(r.get("ok")), "route": "jobretry", "text": r.get("text") or "", "job": r.get("job")}

    if m_cj:
        from nils_job_runtime.accept import accept_task
        from nils_job_runtime import store
        from nils_job_runtime import owner_tasks
        from nils_job_runtime import cursor_safety as safety

        if not safety.cursor_allowed():
            return {
                "ok": True,
                "route": "owner_cursor_disabled",
                "text": "Cursor ist deaktiviert (NILS_CANARY_ALLOW_CURSOR=0).",
            }
        kind = m_cj.group("kind").lower()
        repo_name = m_cj.group("repo")
        task = m_cj.group("task").strip()
        if observation_freeze_active() and kind not in ALLOWED_OBSERVATION_KINDS:
            return {
                "ok": True,
                "route": "observation_blocked_kind",
                "text": (
                    "Beobachtungsphase: nur readonly|branch|report "
                    "(plus failtest kontrolliert). Erweiterung BLOCKED."
                ),
            }
        # Freeze: only canary allowlist repo name
        if observation_freeze_active():
            allowed = (
                os.getenv("NILS_CANARY_REPO_ALLOWLIST") or "cursor-canary-repo"
            ).replace(";", ",")
            names = {p.strip() for p in allowed.split(",") if p.strip()}
            if repo_name not in names:
                return {
                    "ok": True,
                    "route": "observation_blocked_repo",
                    "text": (
                        f"Beobachtungsphase: Repository '{repo_name}' nicht in Allowlist. "
                        "Keine selbstständige Erweiterung."
                    ),
                }
        job_class = _class_for_kind(kind)
        if not job_class:
            return {"ok": True, "route": "owner_bad_kind", "text": f"Unbekannte Art: {kind}"}
        resolved = owner_tasks.resolve_repo(repo_name)
        if not resolved.get("ok"):
            return {
                "ok": True,
                "route": "owner_repo_denied",
                "text": f"Repository nicht erlaubt: {resolved.get('error')}",
            }
        attempt = make_attempt_id()
        built = owner_tasks.build_owner_prompt(
            job_class=job_class,
            job_id="PENDING",
            attempt_id=attempt,
            repo=resolved["path"],
            task=task,
        )
        if not built.get("ok"):
            return {
                "ok": True,
                "route": "owner_task_denied",
                "text": f"Aufgabe abgelehnt: {built.get('error')}",
            }
        summary = (
            f"{kind} repo={repo_name} class={job_class} attempt={attempt} | {task[:300]}"
        )
        res = accept_task(
            task_type="owner_job",
            task_summary=summary,
            chat_id=str(chat_id),
            user_id=str(user_id or chat_id),
            message_id=message_id,
            timeout_seconds=600,
            shadow=False,
            notify_telegram=True,
        )
        job = res.get("job") or {}
        jid = job.get("job_id")
        if jid and not res.get("duplicate"):
            # rebuild prompt with real job id for report path uniqueness is ok via attempt
            store.update_fields(
                jid,
                max_retries=0,
                attempt_id=attempt,
                job_class=job_class,
                workspace_path=str(resolved["path"]),
                git_branch=built.get("branch") if job_class == "BRANCH_CHANGE" else None,
            )
            job = store.get_job(jid) or job
        text_out = res.get("text") or ""
        if jid and jid not in text_out:
            text_out = f"{text_out}\nJob-ID: {jid}\nAttempt: {attempt}\nKlasse: {job_class}"
        return {
            "ok": True,
            "route": "owner_cursorjob",
            "duplicate": res.get("duplicate"),
            "job": job,
            "text": text_out,
        }

    return None

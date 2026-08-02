# -*- coding: utf-8 -*-
"""Highest-priority control commands: Stop / status — before any LLM processing."""
from __future__ import annotations

import re
from typing import Any

STOP_COMMANDS = frozenset(
    {
        "stop",
        "stopp",
        "abbrechen",
        "hör auf",
        "hoer auf",
        "beenden",
        "cancel",
    }
)

_STOP_RE = re.compile(
    r"(?i)^\s*(?:/)?(?:"
    r"stop|stopp|abbrechen|hör\s+auf|hoer\s+auf|beenden|cancel"
    r")\s*[.!]*\s*$"
)

_STATUS_RE = re.compile(
    r"(?i)^\s*(?:/)?"
    r"(?:"
    r"was\s+machst\s+du\s+gerade|"
    r"was\s+machst\s+du|"
    r"status|"
    r"jobstatus|"
    r"wie\s+weit(?:\s+bist\s+du)?|"
    r"läuft\s+meine\s+aufgabe|"
    r"laeuft\s+meine\s+aufgabe"
    r")"
    r"(?:\s+(?P<jid>NILS-[\w-]+))?"
    r"\s*[?!.,]*\s*$"
)

MSG_STOPPED = "Gestoppt. Der laufende Auftrag wurde abgebrochen."
MSG_NO_JOB = "Es läuft aktuell kein Auftrag."
MSG_IDLE = "Aktuell läuft kein Auftrag."


def is_stop_command(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if _STOP_RE.match(t):
        return True
    return t.lower() in STOP_COMMANDS


def is_status_command(text: str) -> bool:
    return bool(_STATUS_RE.match((text or "").strip()))


def parse_status_job_id(text: str) -> str | None:
    m = _STATUS_RE.match((text or "").strip())
    if not m:
        return None
    return m.group("jid")


def handle_stop(*, chat_id: str, user_id: str | None = None) -> dict[str, Any]:
    """Idempotent stop: cancel active job for chat; never starts a new task."""
    from nils_job_runtime import store
    from nils_job_runtime.cancel import request_cancel, cancel_active_for_chat

    active = store.get_single_active_for_chat(str(chat_id))
    if not active:
        return {
            "ok": True,
            "route": "control_stop",
            "text": MSG_NO_JOB,
            "idempotent": True,
            "had_job": False,
        }

    # Prefer dedicated chat-cancel (handles CANCEL_REQUESTED → CANCELLED)
    result = cancel_active_for_chat(str(chat_id))
    if not result.get("ok") and active.get("job_id"):
        result = request_cancel(active["job_id"], chat_id=str(chat_id))

    # Normalize user-facing text per spec (idempotent)
    st = (result.get("job") or {}).get("status") or ""
    if st == "CANCELLED" or result.get("ok"):
        text = MSG_STOPPED
    elif result.get("already_terminal"):
        text = MSG_NO_JOB
    else:
        text = result.get("text") or MSG_STOPPED

    return {
        "ok": True,
        "route": "control_stop",
        "text": text,
        "job": result.get("job"),
        "had_job": True,
        "idempotent": bool(result.get("idempotent")),
    }


def handle_status(*, chat_id: str, text: str = "") -> dict[str, Any]:
    from nils_job_runtime.status_reply import live_status_report

    jid = parse_status_job_id(text)
    report = live_status_report(chat_id=str(chat_id), job_id=jid)
    return {
        "ok": True,
        "route": "control_status",
        "text": report,
    }


_CAPABILITY_RE = re.compile(
    r"(?i)^\s*(?:/)?"
    r"(?:"
    r"was\s+kannst\s+du\s+aktuell|"
    r"was\s+kannst\s+du|"
    r"fähigkeiten|"
    r"faehigkeiten|"
    r"capability(?:\s*-?\s*scan)?|"
    r"inventar\s+capabilities"
    r")"
    r"\s*[?!.,]*\s*$"
)


def is_capability_command(text: str) -> bool:
    return bool(_CAPABILITY_RE.match((text or "").strip()))


def handle_capabilities(*, chat_id: str | None = None, refresh: bool = False) -> dict[str, Any]:
    """Answer from persistent registry only — never static prompt claims."""
    from nils_job_runtime import capability_registry as reg

    reg.ensure_schema()
    reg.seed_catalog()
    if refresh or not reg.list_all() or all(
        (c.get("last_test_status") == "TEST_REQUIRED" and not c.get("last_tested_at"))
        for c in reg.list_all()
    ):
        try:
            from nils_job_runtime import capability_probes as probes

            probes.run_all_probes(persist=True)
        except Exception as e:
            return {
                "ok": False,
                "route": "control_capabilities",
                "text": f"Capability-Scan fehlgeschlagen: {type(e).__name__}. Registry unverändert.",
            }
    text = reg.format_capability_report()
    return {"ok": True, "route": "control_capabilities", "text": text}


_MEMORY_HINT_RE = re.compile(
    r"(?i)("
    r"was\s+habe\s+ich\s+heute\s+gemacht|"
    r"woran\s+haben\s+wir\s+heute|"
    r"welche\s+kunden\s+sind\s+neu|"
    r"welche\s+projekte\s+sind\s+aktiv|"
    r"stand\s+(?:bei\s+)?(?:german\s*golf|pro\s*office|prooffice|shy001|snack\s*house|pil001)|"
    r"german\s*golf\s*guide|"
    r"was\s+hat\s+cursor|"
    r"cursor\s+zuletzt|"
    r"nur\s+geplant|"
    r"was\s+wurde\s+(?:nur\s+geplant|umgesetzt|getestet)|"
    r"was\s+ist\s+produktiv|"
    r"freigaben\s+fehlen|"
    r"welche\s+freigaben|"
    r"widerspruch|konflikt|"
    r"was\s+ist\s+blockiert|blocker|"
    r"agency\s*ged[aä]chtnis|memory\s+seed"
    r")"
)


def is_memory_command(text: str) -> bool:
    return bool(_MEMORY_HINT_RE.search((text or "").strip()))


def handle_memory(*, text: str) -> dict[str, Any]:
    """Answer from Agency Memory store — status + source visible."""
    from agency_memory import queries, seed, store as am_store

    am_store.ensure_schema()
    t = (text or "").strip()
    if re.search(r"(?i)memory\s+seed|ged[aä]chtnis\s+seed", t):
        out = seed.seed_all()
        return {
            "ok": bool(out.get("ok")),
            "route": "control_memory_seed",
            "text": (
                f"Agency Memory Seed: {out.get('count')} Events "
                f"({out.get('duplicates')} Duplikate)."
            ),
        }
    answer = queries.try_answer(t)
    if not answer:
        return {
            "ok": False,
            "route": "control_memory",
            "text": "Keine passende Agency-Memory-Abfrage erkannt.",
        }
    return {"ok": True, "route": "control_memory", "text": answer}


def maybe_handle_control_command(
    *,
    text: str,
    chat_id: str,
    user_id: str | None = None,
) -> dict[str, Any] | None:
    """Return response if text is a control command; else None."""
    t = (text or "").strip()
    if not t:
        return None
    if is_stop_command(t):
        return handle_stop(chat_id=str(chat_id), user_id=user_id)
    if is_status_command(t):
        return handle_status(chat_id=str(chat_id), text=t)
    if is_capability_command(t):
        refresh = bool(re.search(r"(?i)scan|aktuell", t))
        return handle_capabilities(chat_id=str(chat_id), refresh=refresh)
    if is_memory_command(t):
        return handle_memory(text=t)
    return None

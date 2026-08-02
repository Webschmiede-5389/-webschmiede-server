# -*- coding: utf-8 -*-
"""Honest status replies from DB only — never from LLM guesswork."""
from __future__ import annotations

import time
from typing import Any

from nils_job_runtime import queue, store


def _ago(iso: str | None) -> str:
    ts = queue._parse_ts(iso)
    if ts is None:
        return "unbekannt"
    sec = max(0, int(time.time() - ts))
    if sec < 60:
        return f"vor {sec} Sekunden"
    if sec < 3600:
        return f"vor {sec // 60} Minuten"
    return f"vor {sec // 3600} Stunden"


def format_status(job: dict[str, Any]) -> str:
    jid = job["job_id"]
    st = job["status"]
    if st == "RUNNING":
        cur = int(job.get("progress_current") or 0)
        tot = int(job.get("progress_total") or 0)
        step = job.get("progress_message") or job.get("current_step") or "läuft"
        hb = _ago(job.get("last_heartbeat_at"))
        # Refuse to claim working without fresh heartbeat
        lease_ts = queue._parse_ts(job.get("lease_expires_at"))
        if lease_ts is not None and lease_ts < time.time():
            return (
                f"Auftrag {jid} ist als RUNNING markiert, aber das Lease ist abgelaufen "
                f"(letztes Lebenszeichen {hb}). Warte auf Stall-Erkennung."
            )
        # Honest external/cursor wording
        if job.get("external_kind"):
            last = job.get("external_last_step") or "kein Schritt nachgewiesen"
            pid = job.get("external_pid")
            extra = f" Extern: {job.get('external_kind')}"
            if pid:
                extra += f" PID={pid}"
            if job.get("external_ref"):
                extra += f" Ref={job.get('external_ref')}"
            return (
                f"Auftrag {jid} läuft.{extra}. "
                f"Letzter nachgewiesener Schritt: {last}. "
                f"Letztes Lebenszeichen: {hb}. "
                f"{step}"
            )
        if tot > 0:
            return (
                f"Auftrag {jid} läuft. Aktueller Schritt: {cur} von {tot} — {step}. "
                f"Letztes Lebenszeichen: {hb}."
            )
        return f"Auftrag {jid} läuft ({step}). Letztes Lebenszeichen: {hb}."
    if st == "QUEUED":
        ahead = store.queue_ahead_count(jid)
        return (
            f"Auftrag {jid} wartet noch. Vor ihm befinden sich {ahead} Aufträge."
        )
    if st == "RECEIVED":
        return f"Auftrag {jid} wurde empfangen und wird gleich eingereiht."
    if st == "WAITING":
        return f"Auftrag {jid} wartet auf eine externe Voraussetzung (WAITING)."
    if st == "STALLED":
        return (
            f"Auftrag {jid} ist festgefahren. Das letzte Lebenszeichen war "
            f"{job.get('last_heartbeat_at') or 'unbekannt'}. "
            f"Ein automatischer Wiederholungsversuch wurde ggf. eingeplant."
        )
    if st == "TIMED_OUT":
        return (
            f"Auftrag {jid} ist fehlgeschlagen. Ursache: Zeitüberschreitung "
            f"({job.get('error_message_redacted') or 'Timeout'})."
        )
    if st == "FAILED":
        return (
            f"Auftrag {jid} ist fehlgeschlagen. Ursache: "
            f"{job.get('error_message_redacted') or job.get('error_category') or 'unbekannt'}."
        )
    if st == "RESULT_VALIDATION_FAILED":
        return (
            f"Auftrag {jid}: Ergebnisprüfung fehlgeschlagen "
            f"({job.get('result_validation') or job.get('error_message_redacted') or 'invalid'})."
        )
    if st == "CANCEL_REQUESTED":
        return f"Auftrag {jid}: Abbruch angefordert (Prozessgruppe wird gestoppt)."
    if st == "SUCCEEDED":
        ref = job.get("result_reference") or ""
        extra = f" Ergebnisreferenz: {ref}." if ref else ""
        return f"Auftrag {jid} ist fertig (SUCCEEDED).{extra}"
    if st == "COMPLETED":
        ref = job.get("result_reference") or ""
        extra = f" Beleg: {ref}." if ref else ""
        return f"Auftrag {jid} ist fertig (COMPLETED).{extra}"
    if st == "TIMEOUT":
        return (
            f"Auftrag {jid} ist fehlgeschlagen. Ursache: Zeitüberschreitung "
            f"({job.get('error_message_redacted') or 'Timeout'})."
        )
    if st == "NEEDS_CLARIFICATION":
        return (
            f"Auftrag {jid} wartet auf Klärung "
            f"({job.get('progress_message') or 'Angaben fehlen'})."
        )
    if st == "PREFLIGHT":
        return f"Auftrag {jid}: Capability-Preflight läuft."
    if st == "WAITING_FOR_APPROVAL":
        return (
            f"Auftrag {jid}: WAITING_FOR_APPROVAL "
            f"({job.get('approval_required') or 'Freigabe nötig'})."
        )
    if st == "RECOVERY_REQUIRED":
        return (
            f"Auftrag {jid}: RECOVERY_REQUIRED nach Neustart/unklarem Zustand. "
            "Keine stille Wiederholung — bitte prüfen oder abbrechen."
        )
    if st == "CANCELLED":
        return f"Auftrag {jid} wurde abgebrochen."
    return f"Auftrag {jid}: Status {st}."


def eta_text(job: dict[str, Any] | None = None) -> str:
    """Only allow ETA from measurable progress + history; otherwise honest refusal."""
    # Historical comparable jobs not implemented yet → never invent.
    return "Eine belastbare Fertigstellungszeit ist noch nicht verfügbar."


def answer_status_question(
    *,
    chat_id: str,
    job_id: str | None = None,
) -> str:
    if job_id:
        job = store.get_job_for_chat(job_id, chat_id)
        if job is None:
            # distinguish missing vs foreign
            any_job = store.get_job(job_id)
            if any_job is None:
                return f"Auftrag {job_id} wurde nicht gefunden."
            return "Zugriff verweigert: dieser Auftrag gehört nicht zu diesem Chat."
        return format_status(job) + "\n" + eta_text(job)
    active = store.list_active_for_chat(chat_id)
    if not active:
        return "Aktuell sind keine offenen Aufträge für diesen Chat gespeichert."
    lines = [format_status(j) for j in active[:5]]
    return "\n\n".join(lines)


def live_status_report(*, chat_id: str, job_id: str | None = None) -> str:
    """„Was machst du gerade?“ — strictly from SQLite job state."""
    if job_id:
        job = store.get_job_for_chat(job_id, chat_id)
        if not job:
            any_job = store.get_job(job_id)
            if any_job is None:
                return "Aktuell läuft kein Auftrag."
            return "Zugriff verweigert: dieser Auftrag gehört nicht zu diesem Chat."
        return _format_live(job)

    job = store.get_single_active_for_chat(chat_id)
    if not job:
        return "Aktuell läuft kein Auftrag."
    return _format_live(job)


def _format_live(job: dict[str, Any]) -> str:
    return (
        f"Aktive job_id: {job.get('job_id')}\n"
        f"Projekt: {job.get('projekt') or '–'}\n"
        f"Aufgabe: {job.get('task_summary') or job.get('original_request') or '–'}\n"
        f"Status: {job.get('status')}\n"
        f"Gestartetes Tool: {job.get('external_kind') or job.get('capability') or '–'}\n"
        f"Startzeit: {job.get('started_at') or job.get('queued_at') or job.get('created_at') or '–'}\n"
        f"Letzter technischer Fortschritt: "
        f"{job.get('external_last_step') or job.get('progress_message') or job.get('current_step') or '–'}"
    )


def status_message_if_changed(job: dict[str, Any], new_info: str) -> str | None:
    """Only emit when technical state changed vs last_status_notified."""
    key = f"{job.get('status')}|{job.get('progress_current')}|{job.get('external_last_step')}"
    if key == (job.get("last_status_notified") or ""):
        return None
    store.update_fields(job["job_id"], last_status_notified=key)
    return (
        f"job_id={job.get('job_id')} | Projekt={job.get('projekt') or '–'} | "
        f"Status={job.get('status')} | {new_info}"
    )

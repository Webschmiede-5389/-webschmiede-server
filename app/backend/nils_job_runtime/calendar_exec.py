# -*- coding: utf-8 -*-
"""Inline calendar exec for Nils (mock or google backend) + Meeting-Notify."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from nils_job_runtime import calendar_connector as cal
from nils_job_runtime import notify
from nils_job_runtime import store
from nils_job_runtime import turn_context as tc

log = logging.getLogger("nils_job_runtime.calendar_exec")


def format_meeting_set(event: dict[str, Any], *, calendar_id: str = "") -> str:
    title = str(event.get("summary") or event.get("title") or "Termin")
    start = str(event.get("start_iso") or event.get("start") or "–")
    eid = str(event.get("event_id") or event.get("id") or "–")
    return (
        "Meeting gesetzt:\n"
        f"Titel: {title}\n"
        f"Start: {start}\n"
        f"Kalender: {calendar_id or event.get('calendar_id') or '–'}\n"
        f"Beleg: {eid}"
    )


def _parse_draft(text: str, collected: dict[str, Any]) -> cal.EventDraft:
    title = (collected.get("titel") or collected.get("title") or "").strip()
    if not title:
        m = re.search(r"(?i)(?:titel|betreff)\s*[:=]\s*(.+)$", text or "", re.M)
        if m:
            title = m.group(1).strip()[:120]
    if not title:
        m = re.search(
            r"(?i)termin\s+(?:anlegen|erstellen)\s*[:=]?\s*(.+)$", text or "", re.M
        )
        if m:
            title = m.group(1).strip()[:120]
    if not title:
        title = "Nils Termin"

    tz_name = os_getenv_tz()
    tz = ZoneInfo(tz_name)
    t = text or ""
    start_dt = (datetime.now(tz) + timedelta(days=1)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    if collected.get("datum"):
        try:
            raw = str(collected["datum"])
            if re.match(r"\d{4}-\d{2}-\d{2}", raw):
                start_dt = datetime.fromisoformat(raw).replace(tzinfo=tz)
            else:
                parts = re.split(r"[./]", raw)
                if len(parts) >= 2:
                    d, mo = int(parts[0]), int(parts[1])
                    y = int(parts[2]) if len(parts) > 2 else datetime.now(tz).year
                    if y < 100:
                        y += 2000
                    start_dt = start_dt.replace(year=y, month=mo, day=d)
        except Exception:
            pass
    elif re.search(r"(?i)\bheute\b", t):
        start_dt = datetime.now(tz).replace(hour=10, minute=0, second=0, microsecond=0)
    elif re.search(r"(?i)\bmorgen\b", t):
        start_dt = (datetime.now(tz) + timedelta(days=1)).replace(
            hour=10, minute=0, second=0, microsecond=0
        )

    tm = re.search(r"(?i)\b(\d{1,2})[:.](\d{2})\b", t) or re.search(
        r"(?i)\b(\d{1,2})\s*uhr\b", t
    )
    if tm:
        h = int(tm.group(1))
        mi = int(tm.group(2)) if tm.lastindex and tm.lastindex >= 2 else 0
        start_dt = start_dt.replace(hour=min(h, 23), minute=min(mi, 59))

    date_s = start_dt.strftime("%Y-%m-%d")
    time_s = start_dt.strftime("%H:%M")
    return cal.EventDraft(
        title=title,
        date=date_s,
        start_time=time_s,
        duration_minutes=30,
        timezone=tz_name,
        description="Via Nils Telegram",
    )


def os_getenv_tz() -> str:
    import os

    return (os.getenv("NILS_CALENDAR_TZ") or "Europe/Berlin").strip() or "Europe/Berlin"


def execute_calendar(
    *,
    job: dict[str, Any],
    turn: dict[str, Any],
    capability: str,
    approval_granted: bool = False,
    original_text: str = "",
) -> dict[str, Any]:
    from nils_job_runtime import crm_offer_exec as offer_exec

    jid = job["job_id"]
    text = original_text or (job.get("original_request") or "")
    collected = dict(turn.get("collected_parameters") or {})
    conn = cal.CalendarConnector()

    try:
        if capability in ("calendar.read", "calendar.freebusy", "calendar.availability"):
            listed = conn.list_events(limit=15)
            events = listed.get("events") or []
            if not events:
                reply = "Keine Termine im Zielkalender (Fenster/leer)."
            else:
                lines = ["Termine:", ""]
                for e in events[:12]:
                    lines.append(
                        f"· {e.get('start_iso', '?')[:16]} — {e.get('summary', '–')}"
                    )
                reply = "\n".join(lines)
            turn["state"] = tc.STATE_DONE
            tc.save(jid, turn)
            return offer_exec._succeed(
                jid, turn, reply, offer_number="calendar:read"
            )

        if capability == "calendar.prepare":
            draft = _parse_draft(text, collected)
            prep = conn.prepare(draft)
            reply = (
                "Termin vorbereitet (kein Schreib):\n"
                + str(prep.get("payload") or prep)[:800]
            )
            turn["state"] = tc.STATE_DONE
            tc.save(jid, turn)
            return offer_exec._succeed(
                jid, turn, reply, offer_number="calendar:prepare"
            )

        if capability in (
            "calendar.create",
            "calendar.write",
            "calendar.update",
            "calendar.delete",
            "calendar.invite",
        ):
            if not approval_granted:
                draft = _parse_draft(text, collected)
                collected["titel"] = draft.title
                collected["datum"] = draft.date
                collected["uhrzeit_oder_zeitraum"] = draft.start_time
                turn["collected_parameters"] = collected
                turn["state"] = tc.STATE_AWAITING_SALES_APPROVAL
                prompt = (
                    "Freigabe nötig — Kalender:\n"
                    f"Aktion: {capability}\n"
                    f"Titel: {draft.title}\n"
                    f"Start: {draft.date} {draft.start_time}\n"
                    'Antworte mit „ja“, sonst „stop“.'
                )
                tc.save(jid, turn)
                try:
                    job2 = store.get_job(jid)
                    cur = (job2 or {}).get("status")
                    if cur == "RECEIVED":
                        store.transition(
                            jid, "PREFLIGHT", extra={"pipeline_stage": "APPROVAL_CHECK"}
                        )
                        cur = "PREFLIGHT"
                    if cur == "PREFLIGHT":
                        store.transition(
                            jid,
                            "WAITING_FOR_APPROVAL",
                            extra={
                                "approval_required": capability,
                                "capability": capability,
                                "progress_message": f"Warte auf Freigabe: {capability}",
                            },
                        )
                except Exception:
                    log.exception("calendar_park_approval")
                return {
                    "ok": False,
                    "reply": prompt,
                    "job": store.get_job(jid) or job,
                    "turn": turn,
                    "terminal": False,
                }

            draft = _parse_draft(text, collected)
            if capability in ("calendar.create", "calendar.write", "calendar.invite"):
                result = conn.create(
                    draft, approved=True, invite=(capability == "calendar.invite")
                )
            elif capability == "calendar.update":
                eid = str(collected.get("termin_id") or collected.get("event_id") or "")
                if not eid:
                    raise cal.CalendarError("missing_event", "termin_id fehlt")
                start_iso, end_iso = draft.resolve_times()
                result = conn.update(
                    eid,
                    approved=True,
                    summary=draft.title,
                    start_iso=start_iso,
                    end_iso=end_iso,
                )
            else:
                eid = str(collected.get("termin_id") or collected.get("event_id") or "")
                result = conn.delete(eid, approved=True)

            if not result.get("ok"):
                reply = f"Kalender-Fehler: {result}"
                turn["state"] = tc.STATE_FAILED
                tc.save(jid, turn)
                return {
                    "ok": False,
                    "reply": reply,
                    "job": offer_exec._fail(jid, reply, category="calendar_error"),
                    "turn": turn,
                    "terminal": True,
                }

            event = result.get("event") or {}
            reply = format_meeting_set(
                event if isinstance(event, dict) else {"event_id": str(event)},
                calendar_id=str(
                    (event or {}).get("calendar_id")
                    or conn.cfg.allowed_calendar_id
                    or conn.cfg.target_name
                    or ""
                ),
            )
            try:
                notify._send(job.get("telegram_chat_id"), reply)
            except Exception:
                log.exception("calendar_meeting_notify")

            turn["state"] = tc.STATE_DONE
            tc.save(jid, turn)
            return offer_exec._succeed(
                jid, turn, reply, offer_number="calendar:write"
            )

        reply = f"Kalender-Capability unbekannt: {capability}"
        return {
            "ok": False,
            "reply": reply,
            "job": offer_exec._fail(jid, reply, category="unknown_cap"),
            "turn": turn,
            "terminal": True,
        }
    except cal.CalendarError as e:
        reply = f"Kalender: {e.code} — {e.detail}"
        turn["state"] = tc.STATE_FAILED
        tc.save(jid, turn)
        return {
            "ok": False,
            "reply": reply,
            "job": offer_exec._fail(jid, reply, category=e.code),
            "turn": turn,
            "terminal": True,
        }
    except Exception as e:
        log.exception("calendar_exec")
        reply = f"Kalender fehlgeschlagen: {type(e).__name__}: {e}"
        turn["state"] = tc.STATE_FAILED
        tc.save(jid, turn)
        return {
            "ok": False,
            "reply": reply,
            "job": offer_exec._fail(jid, reply, category="calendar_exec"),
            "turn": turn,
            "terminal": True,
        }

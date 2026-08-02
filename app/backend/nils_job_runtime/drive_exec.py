# -*- coding: utf-8 -*-
"""Inline Drive exec — Agency-Sales Root only (Zug F + I)."""
from __future__ import annotations

import logging
import re
from typing import Any

from nils_job_runtime import crm_offer_exec as offer_exec
from nils_job_runtime import drive_connector as drive
from nils_job_runtime import store
from nils_job_runtime import turn_context as tc

log = logging.getLogger("nils_job_runtime.drive_exec")

WRITE_CAPS = frozenset(
    {
        "drive.doc_create",
        "drive.sheet_create",
        "drive.sheet_write",
        "drive.write",
    }
)


def _park_approval(jid: str, turn: dict[str, Any], prompt: str, capability: str) -> None:
    turn["state"] = tc.STATE_AWAITING_SALES_APPROVAL
    tc.save(jid, turn)
    try:
        job = store.get_job(jid)
        assert job
        cur = job["status"]
        if cur == "RECEIVED":
            job = store.transition(
                jid, "PREFLIGHT", extra={"pipeline_stage": "APPROVAL_CHECK"}
            )
            cur = job["status"]
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
        else:
            store.update_fields(
                jid,
                progress_message=prompt[:200],
                capability=capability,
                approval_required=capability,
            )
    except Exception:
        log.exception("drive_park_approval")


def _parse_doc(text: str, collected: dict[str, Any]) -> tuple[str, str]:
    title = str(collected.get("titel") or collected.get("title") or "").strip()
    body = str(collected.get("text") or collected.get("body") or "").strip()
    raw = text or ""
    if not body:
        m = re.search(r"(?i)\b(?:text|body|inhalt)\s*[:=]\s*(.+)$", raw, re.S)
        if m:
            body = m.group(1).strip()
    if not title:
        m = re.search(
            r"(?i)(?:drive\s+)?(?:doc|dokument|notiz|kurzdoc)\s+"
            r"(?:titel|title)\s*[:=]\s*(.+)",
            raw,
        )
        if m:
            title = m.group(1).strip()
    if not title:
        m = re.search(
            r"(?i)(?:leg|lege|erstell\w*|schreib\w*)\s+(?:ein\s+)?"
            r"(?:drive\s+)?(?:doc|dokument|kurzdoc)\s+(.+)$",
            raw,
            re.M,
        )
        if m:
            title = m.group(1).strip()
    if title:
        title = re.split(r"(?i)\b(?:text|body|inhalt)\s*[:=]", title, maxsplit=1)[0].strip()
        title = title[:120]
    if not title:
        title = "Nils Kurzdoc"
    if not body:
        body = "Angelegt via Nils Telegram (Agency-Sales)."
    return title, body


def _clean_sheet_title(title: str) -> str:
    title = re.split(
        r"(?i)\s*(?:zeilen|rows|daten)\s*[:=]",
        title or "",
        maxsplit=1,
    )[0].strip()
    title = re.sub(r"(?i)^\s*(?:schreiben|anlegen|erstellen)\s+", "", title).strip()
    return title[:120]


def _parse_sheet_title(text: str, collected: dict[str, Any]) -> str:
    title = _clean_sheet_title(
        str(collected.get("titel") or collected.get("title") or "").strip()
    )
    if title:
        return title
    m = re.search(
        r"(?i)(?:titel|title)\s*[:=]\s*(.+?)(?=\s*(?:zeilen|rows|daten)\s*[:=]|$)",
        text or "",
        re.S,
    )
    if m:
        cleaned = _clean_sheet_title(m.group(1).strip())
        if cleaned:
            return cleaned
    return "Nils Tabelle"


def _parse_rows(text: str, collected: dict[str, Any]) -> list[list[str]]:
    raw = str(collected.get("zeilen") or collected.get("rows") or "").strip()
    if not raw:
        m = re.search(
            r"(?i)(?:zeilen|rows|daten)\s*[:=]\s*(.+)$",
            text or "",
            re.S,
        )
        if m:
            raw = m.group(1).strip()
    if not raw:
        return []
    rows: list[list[str]] = []
    for part in re.split(r"\s*;\s*|\n+", raw):
        part = part.strip()
        if not part:
            continue
        cells = [c.strip() for c in re.split(r"\s*\|\s*", part)]
        if cells and any(cells):
            rows.append(cells)
    return rows[:100]


def execute_drive(
    *,
    job: dict[str, Any],
    turn: dict[str, Any],
    capability: str,
    approval_granted: bool = False,
    original_text: str = "",
) -> dict[str, Any]:
    jid = job["job_id"]
    text = original_text or (job.get("original_request") or "")
    collected = dict(turn.get("collected_parameters") or {})
    conn = drive.DriveConnector()

    try:
        if capability in ("drive.read", "drive.list"):
            q = ""
            m = re.search(r"(?i)(?:suche|search|mit)\s*[:=]?\s*(.+)$", text or "")
            if m:
                q = m.group(1).strip()[:80]
            listed = conn.list_files(limit=20, query=q)
            reply = drive.format_list(listed)
            turn["state"] = tc.STATE_DONE
            tc.save(jid, turn)
            return offer_exec._succeed(jid, turn, reply, offer_number="drive:list")

        if capability in WRITE_CAPS:
            want_sheet_write = capability == "drive.sheet_write" or bool(
                re.search(
                    r"(?i)\b(?:tabelle|sheet)\s+(?:schreiben|zeilen)|"
                    r"(?:schreib|schreibe)\w*\s+(?:in\s+)?(?:die\s+)?tabelle|"
                    r"\bzeilen\s*[:=]",
                    text or "",
                )
            )
            is_sheet = capability in ("drive.sheet_create", "drive.sheet_write") or bool(
                re.search(r"(?i)\b(tabelle|sheet|spreadsheet)\b", text or "")
            )

            if want_sheet_write and capability != "drive.doc_create":
                capability = "drive.sheet_write"
                title = _parse_sheet_title(text, collected)
                rows = _parse_rows(text, collected)
                if not rows:
                    turn["missing_parameters"] = ["zeilen"]
                    turn["state"] = tc.STATE_WAITING_FOR_INPUT
                    collected["titel"] = title
                    turn["collected_parameters"] = collected
                    prompt = (
                        "Drive Tabelle schreiben — welche Zeilen?\n"
                        "Beispiel: zeilen: Firma|Status|Next ; ProOffice|Onboarding|Anruf"
                    )
                    tc.save(jid, turn)
                    return {
                        "ok": False,
                        "reply": prompt,
                        "job": offer_exec._clarify(jid, prompt, turn),
                        "turn": turn,
                        "terminal": False,
                    }
                collected["titel"] = title
                collected["zeilen"] = " ; ".join("|".join(r) for r in rows)
                turn["collected_parameters"] = collected
                preview = "\n".join(" | ".join(r) for r in rows[:5])
                if len(rows) > 5:
                    preview += f"\n… +{len(rows) - 5} weitere"
                if not approval_granted:
                    prompt = (
                        "Freigabe nötig — Drive Tabelle schreiben:\n"
                        f"Titel: {title}\n"
                        f"Zeilen: {len(rows)}\n"
                        f"{preview}\n"
                        f"Ordner: {conn.cfg.root_name}\n"
                        'Antworte mit „ja“, sonst „stop“.'
                    )
                    _park_approval(jid, turn, prompt, capability)
                    return {
                        "ok": False,
                        "reply": prompt,
                        "job": store.get_job(jid) or job,
                        "turn": turn,
                        "terminal": False,
                    }
                result = conn.write_sheet(title=title, rows=rows, approved=True)
                reply = drive.format_sheet_write(result)

            elif is_sheet and capability != "drive.doc_create":
                capability = "drive.sheet_create"
                title = _parse_sheet_title(text, collected)
                rows = _parse_rows(text, collected)
                collected["titel"] = title
                turn["collected_parameters"] = collected
                if not approval_granted:
                    prompt = (
                        "Freigabe nötig — Drive Tabelle:\n"
                        f"Titel: {title}\n"
                        f"Zeilen: {len(rows) if rows else 0} (leer = nur anlegen)\n"
                        f"Ordner: {conn.cfg.root_name}\n"
                        'Antworte mit „ja“, sonst „stop“.'
                    )
                    _park_approval(jid, turn, prompt, capability)
                    return {
                        "ok": False,
                        "reply": prompt,
                        "job": store.get_job(jid) or job,
                        "turn": turn,
                        "terminal": False,
                    }
                result = conn.create_sheet(
                    title=title, approved=True, rows=rows or None
                )
                reply = drive.format_created(result, kind="Tabelle")
                if rows:
                    reply += f"\nZeilen: {len(rows)}"
            else:
                capability = "drive.doc_create"
                title, body = _parse_doc(text, collected)
                collected["titel"] = title
                collected["text"] = body
                turn["collected_parameters"] = collected
                if not approval_granted:
                    prompt = (
                        "Freigabe nötig — Drive Kurzdoc:\n"
                        f"Titel: {title}\n"
                        f"Text: {body[:160]}{'…' if len(body) > 160 else ''}\n"
                        f"Ordner: {conn.cfg.root_name}\n"
                        'Antworte mit „ja“, sonst „stop“.'
                    )
                    _park_approval(jid, turn, prompt, capability)
                    return {
                        "ok": False,
                        "reply": prompt,
                        "job": store.get_job(jid) or job,
                        "turn": turn,
                        "terminal": False,
                    }
                result = conn.create_doc(title=title, body=body, approved=True)
                reply = drive.format_created(result, kind="Doc")

            turn["state"] = tc.STATE_DONE
            tc.save(jid, turn)
            return offer_exec._succeed(
                jid, turn, reply, offer_number=f"drive:{result.get('id') or 'ok'}"
            )

        reply = f"Drive-Capability unbekannt: {capability}"
        turn["state"] = tc.STATE_FAILED
        tc.save(jid, turn)
        return {
            "ok": False,
            "reply": reply,
            "job": offer_exec._fail(jid, reply, category="unknown_cap"),
            "turn": turn,
            "terminal": True,
        }
    except drive.DriveError as e:
        reply = f"Drive: {e.code} — {e.detail}"
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
        log.exception("drive_exec")
        reply = f"Drive fehlgeschlagen: {type(e).__name__}: {e}"
        turn["state"] = tc.STATE_FAILED
        tc.save(jid, turn)
        return {
            "ok": False,
            "reply": reply,
            "job": offer_exec._fail(jid, reply, category="drive_exec"),
            "turn": turn,
            "terminal": True,
        }

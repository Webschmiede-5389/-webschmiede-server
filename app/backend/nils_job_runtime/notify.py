# -*- coding: utf-8 -*-
"""Telegram / log notifications for Nils jobs (rate-limited)."""
from __future__ import annotations

import logging
import os
import time
from typing import Any

from nils_job_runtime import store

log = logging.getLogger("nils_job_runtime.notify")

PROGRESS_MIN_INTERVAL = int(os.getenv("NILS_JOB_PROGRESS_NOTIFY_SECONDS", "120") or 120)
NOTIFY_ENABLED = (os.getenv("NILS_JOB_NOTIFY", "1") or "1").lower() not in (
    "0",
    "false",
    "no",
    "off",
)


def _send(chat_id: str | None, text: str) -> dict[str, Any]:
    if not NOTIFY_ENABLED:
        log.info("notify_suppressed chat=%s text=%s", chat_id, store.redact(text, 200))
        return {"ok": True, "suppressed": True}
    if not chat_id:
        log.warning("notify_no_chat text=%s", store.redact(text, 120))
        return {"ok": False, "error": "no_chat"}
    try:
        import telegram_ops as tg

        # only owner chats
        if not tg.is_owner_chat(chat_id):
            return {"ok": False, "error": "not_owner"}
        return tg.send_message(chat_id, text[:3800])
    except Exception as e:
        log.exception("telegram notify failed")
        try:
            import urllib.request
            import json as _json

            # fallback ops alert without printing secrets
            # use local ops alert if available
            pass
        except Exception:
            pass
        _ops_alert(f"Nils job notify failed: {store.redact(str(e), 160)}")
        return {"ok": False, "error": store.redact(str(e), 120)}


def _ops_alert(body: str) -> None:
    try:
        import json
        import urllib.request

        secret = os.getenv("CRON_SECRET") or os.getenv("N8N_AUDIT_CRON_SECRET") or ""
        if not secret:
            return
        req = urllib.request.Request(
            "http://127.0.0.1:8000/api/ops/alert",
            data=json.dumps(
                {
                    "title": "Nils Job Runtime",
                    "body": store.redact(body, 400),
                    "system": "nils-job-runtime",
                    "tenant": "agency",
                    "step": "NOTIFY",
                }
            ).encode(),
            headers={
                "Content-Type": "application/json",
                "X-Cron-Secret": secret,
            },
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        log.exception("ops alert failed")


def notify_status(job: dict[str, Any], kind: str, *, force: bool = False) -> dict[str, Any]:
    job_id = job.get("job_id") or "?"
    chat = job.get("telegram_chat_id")
    status = job.get("status")
    # PDF send already delivered the document — avoid duplicate success chatter
    if kind in ("succeeded", "started", "accepted") and (
        job.get("capability") == "crm.offer_pdf_send"
        or job.get("task_type") == "crm.offer_pdf_send"
    ):
        if kind == "succeeded":
            return {"ok": True, "skipped": "pdf_document_is_result"}
        if kind == "started":
            return {"ok": True, "skipped": "pdf_quiet_start"}
    msg = None
    if kind == "accepted":
        msg = (
            f"Auftrag {job_id} wurde angenommen und in die Warteschlange gestellt."
        )
    elif kind == "started":
        msg = f"Auftrag {job_id} wurde gestartet."
    elif kind == "progress":
        if not force:
            last_iso = job.get("notify_last_progress_at")
            if last_iso:
                try:
                    from datetime import datetime

                    last_ts = datetime.fromisoformat(
                        str(last_iso).replace("Z", "+00:00")
                    ).timestamp()
                    if time.time() - last_ts < PROGRESS_MIN_INTERVAL:
                        return {"ok": True, "skipped": "rate_limit"}
                except Exception:
                    pass
        cur = job.get("progress_current") or 0
        tot = job.get("progress_total") or 0
        step = job.get("progress_message") or job.get("current_step") or "arbeitet"
        msg = f"Auftrag {job_id}: Fortschritt {cur}/{tot} — {step}"
        store.update_fields(job_id, notify_last_progress_at=store.utc_now())
    elif kind == "waiting":
        msg = f"Auftrag {job_id} wartet (WAITING)."
    elif kind == "stalled":
        msg = (
            f"Auftrag {job_id} ist festgefahren (STALLED). "
            f"Letztes Lebenszeichen: {job.get('last_heartbeat_at') or 'unbekannt'}."
        )
        _ops_alert(f"STALLED {job_id}")
    elif kind == "timed_out":
        msg = f"Auftrag {job_id} ist wegen Zeitüberschreitung beendet (TIMED_OUT)."
        _ops_alert(f"TIMED_OUT {job_id}")
    elif kind == "failed":
        err = job.get("error_message_redacted") or job.get("error_category") or "unbekannt"
        msg = f"Auftrag {job_id} ist fehlgeschlagen. Ursache: {err}."
        _ops_alert(f"FAILED {job_id}: {err}")
    elif kind == "succeeded":
        ref = job.get("result_reference") or ""
        msg = f"Auftrag {job_id} ist fertig (SUCCEEDED)."
        if ref:
            msg += f" Ergebnis: {ref}"
    elif kind == "cancelled":
        msg = f"Auftrag {job_id} wurde abgebrochen (CANCELLED)."
    else:
        msg = f"Auftrag {job_id}: Status {status}."
    return _send(str(chat) if chat else None, msg)

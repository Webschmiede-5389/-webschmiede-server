# -*- coding: utf-8 -*-
"""Zeitgesteuerter Follow-up-SLA Push an Owner-Telegram (Zug C).

Läuft per systemd timer stündlich; sendet nur in Berlin-Fenstern
(Morgen 07:00–07:59, Abend 18:00–18:59) und max. 1× pro Fenster/Tag.
Gate: NILS_SLA_PUSH=1
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

log = logging.getLogger("nils_job_runtime.sla_push")

STATE_PATH = Path(
    os.getenv("NILS_SLA_PUSH_STATE")
    or "/var/lib/webschmiede/nils-sla-push-state.json"
)
TZ = ZoneInfo(os.getenv("NILS_CALENDAR_TZ") or "Europe/Berlin")
MORNING_HOUR = int(os.getenv("NILS_SLA_PUSH_MORNING_HOUR", "7") or 7)
EVENING_HOUR = int(os.getenv("NILS_SLA_PUSH_EVENING_HOUR", "18") or 18)


def _truthy(name: str, default: str = "0") -> bool:
    return (os.getenv(name) or default).strip().lower() in ("1", "true", "yes", "on")


def _load_state() -> dict:
    try:
        if STATE_PATH.is_file():
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        log.exception("sla_push_state_read")
    return {}


def _save_state(state: dict) -> None:
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        log.exception("sla_push_state_write")


def _window(now: datetime) -> str | None:
    if now.hour == MORNING_HOUR:
        return "morning"
    if now.hour == EVENING_HOUR:
        return "evening"
    return None


def run(*, force: bool = False, kind: str | None = None) -> dict:
    if not _truthy("NILS_SLA_PUSH", "0") and not force:
        return {"ok": True, "skipped": "NILS_SLA_PUSH aus"}
    if not _truthy("NILS_CAP_CRM_SALES_FIELD", "0"):
        return {"ok": False, "skipped": "sales_field cap aus"}

    now = datetime.now(TZ)
    window = kind or _window(now)
    if not window and not force:
        return {"ok": True, "skipped": "ausserhalb Push-Fenster", "hour": now.hour}

    if not force:
        state = _load_state()
        key = f"{now.date().isoformat()}:{window}"
        if state.get("last_key") == key:
            return {"ok": True, "skipped": "bereits gesendet", "key": key}
    else:
        state = _load_state()
        key = f"{now.date().isoformat()}:{window or 'force'}"

    from nils_job_runtime import crm_sales_field_service as crm
    from nils_job_runtime import notify

    if window == "evening" or kind == "evening":
        text = crm.evening_debrief_text()
    elif kind == "funnel" or (
        window == "morning"
        and now.weekday() == 0
        and _truthy("NILS_FUNNEL_PUSH_MONDAY", "1")
    ):
        # Montag-Morgen: volles Morgen-Briefing + Funnel-Review
        text = crm.morning_briefing_text() + "\n\n" + crm.funnel_review_text(days=7)
    elif window == "morning" or kind == "morning":
        text = crm.morning_briefing_text()
    else:
        text = crm.sla_report_text()

    try:
        import telegram_ops as tg

        owners = tg.owner_chat_ids()
    except Exception as e:
        return {"ok": False, "error": f"telegram_ops: {e}"}
    if not owners:
        return {"ok": False, "error": "kein TELEGRAM_OWNER_CHAT_ID"}

    results = []
    for chat in owners:
        results.append(notify._send(str(chat), text[:3800]))

    state["last_key"] = key
    state["last_at"] = now.isoformat()
    state["last_window"] = window or "force"
    _save_state(state)
    return {
        "ok": all(r.get("ok") for r in results),
        "window": window,
        "key": key,
        "results": results,
        "chars": len(text),
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    argv = list(argv or sys.argv[1:])
    force = "--force" in argv
    kind = None
    if "--evening" in argv:
        kind = "evening"
    elif "--funnel" in argv:
        kind = "funnel"
    elif "--morning" in argv:
        kind = "morning"
    # Load .env when run as CLI
    env_path = Path("/root/app/backend/.env")
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v)
    out = run(force=force, kind=kind)
    print(json.dumps({k: v for k, v in out.items() if k != "results"}, ensure_ascii=False))
    return 0 if out.get("ok") or out.get("skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())

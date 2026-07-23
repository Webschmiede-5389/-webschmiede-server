# -*- coding: utf-8 -*-
"""ETA-Ehrlichkeit: keine Fake-Minutenversprechen. Jobs mit Deadline tracken."""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("nils_eta")

STATE = Path(os.getenv("NILS_JOBS_STATE", "/var/lib/webschmiede/nils-jobs.json"))
if os.name == "nt":
    STATE = Path(__file__).resolve().parents[2] / "agency" / "nils-jobs.json"

_LOCK = threading.Lock()

# „in 5 Minuten“, „dauert 10 min“, „gleich in 2 Minuten fertig“
FAKE_ETA_RE = re.compile(
    r"(?i)("
    r"(?:in|innerhalb\s+von|nach)\s+\d{1,3}\s*(?:min(?:ute(?:n)?)?|m|sekunden|sek|s)\b"
    r"|dauert\s+(?:nur\s+)?\d{1,3}\s*(?:min(?:ute(?:n)?)?|m)\b"
    r"|(?:bin|melde\s+mich|fertig)\s+(?:in|gleich)\s+\d{1,3}\s*(?:min(?:ute(?:n)?)?|m)\b"
    r")"
)

BAN_PHRASES = (
    "gleich fertig",
    "bin noch dran",
    "recherchiere im hintergrund",
    "arbeit im hintergrund",
    "melde mich in",
)


def max_job_minutes() -> int:
    try:
        return max(5, int(float(os.getenv("NILS_JOB_MAX_MINUTES", "25") or 25)))
    except Exception:
        return 25


def strip_fake_etas(text: str) -> str:
    """Entfernt/ersetzt Fake-Zeitversprechen."""
    t = text or ""
    if not t.strip():
        return t
    t2 = FAKE_ETA_RE.sub("sobald es fertig ist", t)
    t2 = re.sub(r"(?i)\bich\s+sobald\b", "Ich melde mich, sobald", t2)
    t2 = re.sub(r"(?i)\bmelde mich sobald\b", "melde mich, sobald", t2)
    low = t2.lower()
    for p in BAN_PHRASES:
        if p in low:
            lines = []
            for line in t2.splitlines():
                if p in line.lower() and ("min" in line.lower() or "hintergrund" in line.lower() or "gleich fertig" in line.lower()):
                    if "hintergrund" in line.lower():
                        continue
                    lines.append("Ich melde mich, wenn’s fertig ist. Keine Minuten-Schätzung.")
                else:
                    lines.append(line)
            t2 = "\n".join(lines)
            low = t2.lower()
    return t2.strip() or t


def eta_system_rules() -> str:
    return (
        "ZEIT-REGEL: Versprich NIEMALS „in X Minuten“ oder „gleich fertig“. "
        "Lange Jobs: „Ich starte das. Wenn fertig, melde ich mich.“ "
        "Nur wenn ein echter Timer/Job läuft, darfst du den Status nennen, keine Uhrzeit raten."
    )


def _load() -> dict[str, Any]:
    try:
        if STATE.is_file():
            return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"jobs": {}}


def _save(data: dict[str, Any]) -> None:
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        log.exception("save jobs")


def register_job(
    job_id: str,
    *,
    kind: str,
    task: str = "",
    max_minutes: int | None = None,
) -> dict[str, Any]:
    mid = max_minutes or max_job_minutes()
    now = time.time()
    with _LOCK:
        data = _load()
        data.setdefault("jobs", {})[job_id] = {
            "job_id": job_id,
            "kind": kind,
            "task": (task or "")[:400],
            "started_at": now,
            "deadline_at": now + mid * 60,
            "max_minutes": mid,
            "status": "running",
            "notified_overdue": False,
        }
        _save(data)
    return data["jobs"][job_id]


def finish_job(job_id: str, *, status: str = "done", detail: str = "") -> None:
    with _LOCK:
        data = _load()
        job = (data.get("jobs") or {}).get(job_id)
        if not job:
            return
        job["status"] = status
        job["finished_at"] = time.time()
        if detail:
            job["detail"] = detail[:500]
        data["jobs"][job_id] = job
        _save(data)


def scan_overdue(*, notify: bool = True) -> dict[str, Any]:
    now = time.time()
    overdue: list[dict[str, Any]] = []
    with _LOCK:
        data = _load()
        jobs = data.get("jobs") or {}
        for jid, job in list(jobs.items()):
            if job.get("status") != "running":
                continue
            if now <= float(job.get("deadline_at") or 0):
                continue
            overdue.append(dict(job))
            if notify and not job.get("notified_overdue"):
                job["notified_overdue"] = True
                jobs[jid] = job
        data["jobs"] = jobs
        _save(data)

    messages = []
    for job in overdue:
        elapsed = int((now - float(job.get("started_at") or now)) / 60)
        msg = (
            f"Job-Watchdog: {job.get('kind')} {job.get('job_id')} läuft schon ~{elapsed} Min "
            f"(Limit {job.get('max_minutes')}). "
            f"Auftrag: {(job.get('task') or '')[:120]}. "
            f"Ich überwache weiter. Status: „cursor status {job.get('job_id')}“."
        )
        messages.append(msg)
        if notify:
            try:
                import telegram_ops as tg

                tg.notify_owner(msg)
            except Exception:
                log.exception("overdue notify")

    return {"ok": True, "overdue": overdue, "messages": messages}

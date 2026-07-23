"""Watchdog-Schränke: flock, Alert-Cooldown, Reparatur-Budget.

Verhindert Server-Überlast und Mail-Spam bei Dauerfehlern.
Standard-Takt der Crons: 10–15 Minuten (nicht Sekunden).
"""
from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator


STATE_DIR = Path(os.getenv("WATCHDOG_CABINET_DIR", "/var/lib/webschmiede/cabinets"))
DEFAULT_ALERT_COOLDOWN_H = float(os.getenv("WATCHDOG_ALERT_COOLDOWN_H", "4"))
DEFAULT_REPAIR_MAX_PER_H = int(os.getenv("WATCHDOG_REPAIR_MAX_PER_H", "2"))


def _state_path(name: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)[:120]
    return STATE_DIR / f"{safe}.json"


def _load(name: str) -> dict:
    path = _state_path(name)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save(name: str, data: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = _state_path(name)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


@contextmanager
def flock(name: str, *, blocking: bool = False) -> Iterator[bool]:
    """Exklusives Lock. blocking=False → bei Belegt sofort skip (False)."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = STATE_DIR / f"{name}.lock"
    fh = open(lock_path, "a+", encoding="utf-8")
    got = False
    try:
        flags = fcntl.LOCK_EX if blocking else (fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            fcntl.flock(fh.fileno(), flags)
            got = True
        except BlockingIOError:
            got = False
        yield got
    finally:
        if got:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        fh.close()


def can_alert(key: str, *, cooldown_hours: float | None = None) -> bool:
    hours = DEFAULT_ALERT_COOLDOWN_H if cooldown_hours is None else cooldown_hours
    state = _load(f"alert_{key}")
    last = state.get("last")
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last)
    except ValueError:
        return True
    return datetime.now() - last_dt >= timedelta(hours=hours)


def record_alert(key: str) -> None:
    _save(f"alert_{key}", {"last": datetime.now().isoformat(timespec="seconds")})


def can_repair(key: str, *, max_per_hour: int | None = None) -> bool:
    limit = DEFAULT_REPAIR_MAX_PER_H if max_per_hour is None else max_per_hour
    state = _load(f"repair_{key}")
    stamps = state.get("stamps") or []
    cutoff = datetime.now() - timedelta(hours=1)
    recent = []
    for s in stamps:
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            continue
        if dt >= cutoff:
            recent.append(s)
    return len(recent) < limit


def record_repair(key: str) -> None:
    state = _load(f"repair_{key}")
    stamps = state.get("stamps") or []
    stamps.append(datetime.now().isoformat(timespec="seconds"))
    # keep 24h
    cutoff = datetime.now() - timedelta(hours=24)
    kept = []
    for s in stamps:
        try:
            if datetime.fromisoformat(s) >= cutoff:
                kept.append(s)
        except ValueError:
            pass
    _save(f"repair_{key}", {"stamps": kept[-50:]})


def fingerprint(parts: list[str]) -> str:
    raw = "|".join(sorted(parts))[:200]
    return "".join(c if c.isalnum() else "_" for c in raw)[:80] or "empty"

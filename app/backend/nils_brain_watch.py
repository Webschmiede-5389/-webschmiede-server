# -*- coding: utf-8 -*-
"""Nils-Hirn-Wächter + Night-Worker: prüfen, soft-reparieren, melden."""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("nils_brain_watch")

STATE = Path(
    os.getenv("NILS_BRAIN_WATCH_STATE", "/var/lib/webschmiede/nils-brain-watch.json")
)
if os.name == "nt":
    STATE = Path(__file__).resolve().parents[2] / "agency" / "nils-brain-watch.json"

DB_CANDIDATES = (
    Path("/root/app/backend/snack.db"),
    Path("/root/app/data/snack.db"),
    Path(__file__).resolve().parents[1] / "snack.db",
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _env(name: str, default: str = "") -> str:
    v = (os.environ.get(name) or "").strip()
    if v:
        return v
    for base in (Path("/root/app"), Path(__file__).resolve().parents[2]):
        for fname in ("cursor.secrets.local", "deploy.secrets.local", "backend/.env"):
            p = base / fname if "backend" not in fname else base / "backend" / ".env"
            if not p.is_file():
                continue
            try:
                for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                    s = line.strip()
                    if not s or s.startswith("#") or "=" not in s:
                        continue
                    k, _, val = s.partition("=")
                    if k.strip() == name:
                        return val.strip().strip('"').strip("'")
            except Exception:
                continue
    return default


def _find_db() -> Path | None:
    for p in DB_CANDIDATES:
        if p.is_file():
            return p
    return None


def check_api_health() -> dict[str, Any]:
    url = "https://digitalehandwerkskunst.de/api/health"
    try:
        with urllib.request.urlopen(url, timeout=12) as r:
            ok = 200 <= int(r.status) < 400
            return {"ok": ok, "status": r.status, "url": url}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160], "url": url}


def check_telegram_webhook() -> dict[str, Any]:
    token = _env("TELEGRAM_BOT_TOKEN")
    if not token:
        return {"ok": False, "error": "no_token"}
    try:
        url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
        res = data.get("result") or {}
        wh = (res.get("url") or "").strip()
        pending = int(res.get("pending_update_count") or 0)
        last_err = (res.get("last_error_message") or "").strip()
        ok = bool(wh) and not last_err and pending < 50
        return {
            "ok": ok,
            "url": wh[:120],
            "pending": pending,
            "last_error": last_err[:200],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def release_stuck_chat_locks(*, max_age_sec: int = 600) -> dict[str, Any]:
    db_path = _find_db()
    if not db_path:
        return {"ok": True, "released": 0, "note": "no_db"}
    released = 0
    try:
        db = sqlite3.connect(str(db_path), timeout=10)
        now = time.time()
        rows = db.execute(
            "SELECT chat_id, locked_at FROM telegram_chat_locks"
        ).fetchall()
        for chat_id, locked_at in rows:
            try:
                age = now - float(locked_at or 0)
            except Exception:
                age = 99999
            if age >= max_age_sec:
                db.execute("DELETE FROM telegram_chat_locks WHERE chat_id=?", (chat_id,))
                released += 1
        # verwaiste claims
        db.execute(
            "UPDATE telegram_updates SET status='abandoned', finished_at=? "
            "WHERE status='processing' AND created_at < ?",
            (now, now - max_age_sec),
        )
        db.commit()
        db.close()
    except Exception as e:
        return {"ok": False, "error": str(e)[:160], "released": released}
    return {"ok": True, "released": released}


def check_github_ready() -> dict[str, Any]:
    try:
        import nils_git_deploy as gd

        tok = bool(gd.github_token())
        return {
            "ok": tok,
            "auto_deploy": gd.auto_deploy_enabled(),
            "token": tok,
            "hint": None if tok else "GITHUB_TOKEN fehlt – Auto-Deploy nur vom Laptop",
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def repair_api_if_needed(health: dict[str, Any]) -> dict[str, Any]:
    if health.get("ok"):
        return {"ok": True, "repaired": False}
    try:
        import subprocess

        p = subprocess.run(
            ["systemctl", "restart", "snack-api"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        time.sleep(3)
        again = check_api_health()
        return {
            "ok": again.get("ok"),
            "repaired": True,
            "restart_code": p.returncode,
            "health_after": again,
        }
    except Exception as e:
        return {"ok": False, "repaired": False, "error": str(e)[:160]}


def run(*, notify: bool = True, night: bool = False) -> dict[str, Any]:
    """Prüfen + soft-fix. Night=True = ausführlicher Report."""
    actions: list[str] = []
    health = check_api_health()
    if not health.get("ok"):
        rep = repair_api_if_needed(health)
        actions.append(f"api_repair={rep}")
        health = rep.get("health_after") or health

    tg = check_telegram_webhook()
    locks = release_stuck_chat_locks()
    if locks.get("released"):
        actions.append(f"locks_released={locks['released']}")

    try:
        import nils_eta as eta

        overdue = eta.scan_overdue(notify=notify)
        if overdue.get("overdue"):
            actions.append(f"overdue_jobs={len(overdue['overdue'])}")
    except Exception as e:
        overdue = {"ok": False, "error": str(e)[:120]}

    gh = check_github_ready()

    # Guardian light
    guardian = {}
    try:
        import ops_guardian as g

        guardian = {"status": (g.status() or {}).get("status")}
    except Exception as e:
        guardian = {"error": str(e)[:80]}

    lines = [
        f"Nils-Hirn-Wächter · {_now()}",
        f"API: {'ok' if health.get('ok') else 'FAIL'}",
        f"Telegram-Webhook: {'ok' if tg.get('ok') else 'PROBLEM'} pending={tg.get('pending')} err={tg.get('last_error') or '–'}",
        f"Chat-Locks freigegeben: {locks.get('released', 0)}",
        f"GitHub-Token: {'ja' if gh.get('token') else 'fehlt'}",
        f"Guardian: {guardian.get('status') or guardian.get('error') or '?'}",
    ]
    if actions:
        lines.append("Aktionen: " + "; ".join(actions))
    if not gh.get("token"):
        lines.append("Hinweis: GITHUB_TOKEN setzen für Auto-Deploy unterwegs.")

    text = "\n".join(lines)
    out = {
        "ok": bool(health.get("ok")) and bool(tg.get("ok") or tg.get("error") == "no_token"),
        "text": text,
        "health": health,
        "telegram": tg,
        "locks": locks,
        "overdue": overdue,
        "github": gh,
        "guardian": guardian,
        "actions": actions,
        "night": night,
    }

    # Notify nur bei Problemen oder Night-Digest
    problem = (not health.get("ok")) or (
        tg.get("last_error") or (tg.get("pending") or 0) >= 20
    ) or bool((overdue or {}).get("overdue")) or bool(locks.get("released"))
    if notify and (problem or night):
        try:
            import telegram_ops as tgops

            prefix = "Nacht-Check:\n" if night else "Hirn-Wächter:\n"
            tgops.notify_owner((prefix + text)[:3800])
        except Exception:
            log.exception("brain watch notify")

    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    except Exception:
        pass
    return out

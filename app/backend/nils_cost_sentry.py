# -*- coding: utf-8 -*-
"""Kosten-Wächter: automatische Jobs finden, teure stoppen oder melden."""
from __future__ import annotations

import logging
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("nils_cost_sentry")

STATE = Path(
    os.getenv("NILS_COST_SENTRY_STATE", "/var/lib/webschmiede/cost-sentry-state.json")
)
if os.name == "nt":
    STATE = Path(__file__).resolve().parents[2] / "agency" / "cost-sentry-state.json"

# Cron-Zeilen die Geld kosten können (Places, Hetzner, Retell, …)
COSTLY_PATTERNS = (
    (r"buyer|hetzner.?buy|server.?buy", "hetzner_buyer", True),  # immer stoppen
    (r"akquise_nightly|akquise_run", "akquise_places", False),  # melden; pausieren wenn Flag
    (r"jay.?voice|retell", "retell_voice", False),
    (r"firecrawl", "firecrawl", False),
)


def _env(name: str, default: str = "") -> str:
    v = (os.environ.get(name) or "").strip()
    if v:
        return v
    for base in (Path("/root/app"), Path(__file__).resolve().parents[2]):
        for fname in ("deploy.secrets.local", "requesty.secrets.local", "cursor.secrets.local", "backend/.env"):
            p = base / fname if not fname.startswith("backend") else base / "backend" / ".env"
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


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _crontab_list() -> str:
    try:
        p = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10)
        return p.stdout or ""
    except Exception:
        return ""


def _crontab_set(body: str) -> bool:
    try:
        p = subprocess.run(
            ["crontab", "-"],
            input=body,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return p.returncode == 0
    except Exception:
        return False


def scan_crontab() -> list[dict[str, Any]]:
    text = _crontab_list()
    found: list[dict[str, Any]] = []
    for line in text.splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        low = raw.lower()
        for pat, kind, force_stop in COSTLY_PATTERNS:
            if re.search(pat, low):
                found.append(
                    {
                        "kind": kind,
                        "force_stop": force_stop,
                        "line": raw[:240],
                    }
                )
                break
    return found


def pause_akquise_default() -> bool:
    """Akquise-Nacht pausieren bis Christian OK (Places-Kosten)."""
    flag = (_env("NILS_PAUSE_AKQUISE_AUTO", "1") or "1").lower()
    return flag not in ("0", "false", "no", "off")


def apply_stops(found: list[dict[str, Any]]) -> dict[str, Any]:
    """Entfernt Buyer immer; Akquise wenn Pause-Flag."""
    text = _crontab_list()
    if not text.strip():
        return {"ok": True, "removed": [], "note": "kein crontab"}
    lines = text.splitlines()
    removed: list[str] = []
    keep: list[str] = []
    for line in lines:
        low = line.lower()
        drop = False
        if re.search(r"buyer|hetzner.?buy|server.?buy", low) and not line.strip().startswith("#"):
            drop = True
            removed.append("hetzner_buyer: " + line.strip()[:120])
        elif pause_akquise_default() and re.search(r"akquise_nightly|akquise_run", low) and not line.strip().startswith("#"):
            drop = True
            removed.append("akquise_places: " + line.strip()[:120])
        if drop:
            keep.append("# [nils-cost-sentry paused] " + line)
        else:
            keep.append(line)
    if removed:
        ok = _crontab_set("\n".join(keep) + "\n")
        return {"ok": ok, "removed": removed}
    return {"ok": True, "removed": []}


def requesty_spend() -> dict[str, Any]:
    try:
        import requesty_client as rc

        return {
            "ok": True,
            "text": rc.spend_status_text(),
            "usage": rc.usage_today(force=False),
            "key": rc.key_info(force=False),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def run(*, apply: bool = True, notify: bool = True) -> dict[str, Any]:
    found = scan_crontab()
    stopped = apply_stops(found) if apply else {"ok": True, "removed": [], "dry": True}
    spend = requesty_spend()
    alerts: list[str] = []
    for f in found:
        alerts.append(f"Auto-Job potenziell kostenpflichtig: {f['kind']} → {f['line'][:100]}")
    if stopped.get("removed"):
        for r in stopped["removed"]:
            alerts.append(f"Gestoppt/pausiert: {r}")
    # Budget soft
    try:
        import requesty_client as rc

        g = rc.budget_guard(kind="image")
        if not g.get("ok") and g.get("error") in ("budget_exceeded", "monthly_budget_exceeded"):
            alerts.append(
                f"Requesty-Budget: {g.get('error')} spend={g.get('spend')} limit={g.get('limit')}"
            )
    except Exception:
        pass

    text_lines = [
        f"Nils Kosten-Wächter · {_now()}",
        f"Gefunden: {len(found)} verdächtige Cron-Zeilen.",
    ]
    if stopped.get("removed"):
        text_lines.append("Pausiert (keine stillen Kosten):")
        text_lines.extend("• " + x for x in stopped["removed"])
        text_lines.append("Akquise wieder an: NILS_PAUSE_AKQUISE_AUTO=0 und Cron neu setzen.")
    else:
        text_lines.append("Nichts gestoppt (oder schon sauber).")
    if spend.get("ok"):
        if spend.get("text"):
            text_lines.append(spend["text"])
        else:
            usage = spend.get("usage") or {}
            key = spend.get("key") or {}
            text_lines.append(
                f"Requesty: Tag≈{usage.get('spend', '?')} / Monat≈{key.get('monthly_spend', '?')}"
            )
    text_lines.append(
        "Cursor/Bilder/Mails nur nach Freigabe. Keine Hetzner-Käufe ohne OK."
    )
    report = "\n".join(text_lines)

    if notify and (stopped.get("removed") or any(f.get("force_stop") for f in found)):
        try:
            import telegram_ops as tg

            tg.notify_owner(report[:3500])
        except Exception:
            log.exception("cost_sentry notify")

    STATE.parent.mkdir(parents=True, exist_ok=True)
    try:
        import json

        STATE.write_text(
            json.dumps(
                {"at": _now(), "found": found, "stopped": stopped, "spend": spend},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass

    return {
        "ok": True,
        "found": found,
        "stopped": stopped,
        "spend": spend,
        "text": report,
        "alerts": alerts,
    }

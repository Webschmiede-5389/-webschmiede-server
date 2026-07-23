# -*- coding: utf-8 -*-
"""Täglicher Server-Report an Christian (Telegram + optional Mail)."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("nils_daily_report")


def _env(name: str, default: str = "") -> str:
    v = (os.environ.get(name) or "").strip()
    if v:
        return v
    for base in (Path("/root/app"), Path(__file__).resolve().parents[2]):
        for fname in ("deploy.secrets.local", "requesty.secrets.local", "backend/.env"):
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


def _now_local() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def build_report() -> dict[str, Any]:
    lines = [f"Nils Tagesreport · {_now_local()}", ""]

    # Guardian
    try:
        import ops_guardian as g

        st = g.status() if hasattr(g, "status") else {}
        status = st.get("status") or st.get("level") or "?"
        lines.append(f"Ops: {status}")
        if st.get("summary"):
            lines.append(str(st["summary"])[:240])
    except Exception as e:
        lines.append(f"Ops: (nicht lesbar) {e}")

    # Health
    try:
        import urllib.request

        with urllib.request.urlopen("https://digitalehandwerkskunst.de/api/health", timeout=10) as r:
            lines.append(f"API health: HTTP {r.status}")
    except Exception as e:
        lines.append(f"API health: FAIL {e}")

    # Kosten
    try:
        import nils_cost_sentry as cost

        # nur scannen, nicht nochmal pausieren (außer buyer)
        c = cost.run(apply=True, notify=False)
        lines.append("")
        lines.append(c.get("text") or "Kosten: ok")
    except Exception as e:
        lines.append(f"Kosten: {e}")

    # Cursor / Deploy Flags
    try:
        import nils_cursor_bridge as bridge
        import nils_git_deploy as gd

        lines.append("")
        lines.append(
            f"Cursor: {'bereit' if bridge.enabled() else 'aus'} · "
            f"Auto-Deploy: {'an' if gd.auto_deploy_enabled() else 'aus'} · "
            f"GitHub-Token: {'ja' if gd.github_token() else 'fehlt (Deploy von Laptop)'}"
        )
    except Exception:
        pass

    # Crontab Kurz
    try:
        import subprocess

        p = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=8)
        cron = p.stdout or ""
        active = [ln for ln in cron.splitlines() if ln.strip() and not ln.strip().startswith("#")]
        lines.append(f"Aktive Cron-Jobs: {len(active)}")
        paused = [ln for ln in cron.splitlines() if "nils-cost-sentry paused" in ln]
        if paused:
            lines.append(f"Pausierte Kosten-Jobs: {len(paused)}")
    except Exception:
        pass

    lines.append("")
    lines.append("Bei Unklarheit: Telegram „inventar“ oder „budget“.")
    text = "\n".join(lines)
    return {"ok": True, "text": text, "at": _now_local()}


def send_report(*, mail: bool = True, telegram: bool = True) -> dict[str, Any]:
    data = build_report()
    text = data.get("text") or ""
    results: dict[str, Any] = {"report": data}

    if telegram:
        try:
            import telegram_ops as tg

            results["telegram"] = tg.notify_owner(text[:3900])
        except Exception as e:
            results["telegram"] = {"ok": False, "error": str(e)[:160]}

    if mail:
        try:
            to = _env("AGENCY_OWNER_EMAIL")
            if to:
                from agency_mail import send_html_email

                safe = (
                    text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                )
                html = f"<pre style='font-family:sans-serif;white-space:pre-wrap'>{safe}</pre>"
                send_html_email(
                    to=to,
                    subject=f"Nils Tagesreport {datetime.now(timezone.utc).date().isoformat()}",
                    html=html,
                    text=text,
                )
                results["mail"] = {"ok": True}
            else:
                results["mail"] = {"ok": False, "skipped": True, "detail": "AGENCY_OWNER_EMAIL fehlt"}
        except Exception as e:
            results["mail"] = {"ok": False, "error": str(e)[:200]}

    return results

#!/usr/bin/env python3
"""
Kunden-Portal-Watchdog: prüft Bestell-/Admin-URLs aus kunden/*.json.

- Schränke: flock, Alert-Cooldown, max. snack-api Restarts/h
- Cron: alle 15 Min (web oder auto)
"""
from __future__ import annotations

import json
import os
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
BERLIN = ZoneInfo("Europe/Berlin")


def _backend_path() -> Path:
    for p in (Path("/root/app/backend"), ROOT / "app" / "backend"):
        if p.is_dir():
            return p
    return ROOT / "app" / "backend"


sys.path.insert(0, str(_backend_path()))
sys.path.insert(0, str(ROOT))

from watchdog_cabinets import (  # noqa: E402
    can_alert,
    can_repair,
    fingerprint,
    flock,
    record_alert,
    record_repair,
)


def _ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _secrets() -> dict[str, str]:
    out: dict[str, str] = {}
    for path in (Path("/root/app/deploy.secrets.local"), ROOT / "deploy.secrets.local"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            out[k.strip()] = v.strip()
        break
    return out


def _kunden_dirs() -> list[Path]:
    return [p for p in (Path("/root/app/kunden"), ROOT / "kunden") if p.is_dir()]


def load_portal_targets() -> list[dict]:
    targets = []
    seen = set()
    for d in _kunden_dirs():
        for path in sorted(d.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            kid = data.get("id") or path.stem.split("_")[0]
            urls = data.get("urls") or {}
            checks = []
            for key in ("test_bestellen", "test_hauptseite", "test_admin"):
                u = (urls.get(key) or "").strip()
                if u:
                    checks.append((key, u))
            # Subdomain-API health if subdomain set
            sub = (urls.get("subdomain") or "").strip()
            if sub:
                checks.append(("api_health", f"https://{sub}.digitalehandwerkskunst.de/api/health"))
            if not checks:
                continue
            sig = (kid, tuple(u for _, u in checks))
            if sig in seen:
                continue
            seen.add(sig)
            targets.append({"id": kid, "name": data.get("name") or kid, "checks": checks})
    return targets


def http_check(url: str) -> tuple[bool, str]:
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "webschmiede-portal-watchdog/1"})
    try:
        with urllib.request.urlopen(req, timeout=20, context=_ssl_ctx()) as resp:
            code = resp.status
            ok = 200 <= code < 500  # 401/403 = Seite da
            if "/api/health" in url:
                body = resp.read().decode("utf-8", "replace")[:80]
                ok = ok and ("ok" in body.lower() or "status" in body.lower() or body.strip().startswith("{"))
            return ok, f"HTTP {code}"
    except urllib.error.HTTPError as e:
        # Portal HTML kann 200 sein; API 401 selten
        if e.code in (401, 403):
            return True, f"HTTP {e.code}"
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)[:120]


def restart_snack_api() -> bool:
    if not Path("/usr/bin/systemctl").is_file():
        return False
    r = subprocess.run(
        ["systemctl", "restart", "snack-api"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return r.returncode == 0


def send_mail(subject: str, text: str, secrets: dict) -> None:
    for k, v in secrets.items():
        os.environ.setdefault(k, v)
    try:
        from agency_mail import send_html_email
    except ImportError:
        return
    to = (secrets.get("AGENCY_OWNER_EMAIL") or secrets.get("AGENCY_SMTP_USER") or "").strip()
    if not to:
        return
    html = f"<pre style='font-family:system-ui'>{text.replace('<', '&lt;')}</pre>"
    send_html_email(to=to, subject=subject, html=html, text=text)


def main() -> int:
    dry = "--dry-run" in sys.argv
    now = datetime.now(BERLIN).strftime("%Y-%m-%d %H:%M %Z")

    with flock("customer_portal", blocking=False) as got:
        if not got:
            print("skip: customer_portal flock belegt")
            return 0

        secrets = _secrets()
        targets = load_portal_targets()
        if not targets:
            print("Keine Kunden-Portale in kunden/*.json")
            return 0

        issues: list[str] = []
        repairs: list[str] = []
        lines = [f"Kunden-Portal-Watchdog {now}", ""]

        for t in targets:
            lines.append(f"{t['id']} ({t['name']}):")
            kid_fail = False
            for label, url in t["checks"]:
                ok, detail = http_check(url)
                mark = "OK" if ok else "FAIL"
                lines.append(f"  [{mark}] {label}: {detail}  {url}")
                if not ok:
                    kid_fail = True
                    issues.append(f"{t['id']} {label}: {detail}")
            if kid_fail:
                host = urlparse(t["checks"][0][1]).hostname or ""
                # Nur auf dem Web-Server snack-api restarten
                if host and not dry and Path("/etc/systemd/system/snack-api.service").is_file():
                    if can_repair("snack_api_restart", max_per_hour=2):
                        if restart_snack_api():
                            record_repair("snack_api_restart")
                            repairs.append(f"snack-api restart wegen {t['id']}")
                            lines.append("  -> snack-api neu gestartet")
                        else:
                            lines.append("  -> snack-api restart fehlgeschlagen")
                    else:
                        lines.append("  -> Schrank: snack-api Restart-Budget leer")

        text = "\n".join(lines)
        print(text)

        log = Path("/var/log/customer-portal-watchdog.log")
        try:
            with open(log, "a", encoding="utf-8") as f:
                f.write(f"\n===== {now} =====\n{text}\n")
        except OSError:
            pass

        if issues and not dry:
            fp = fingerprint(issues)
            if can_alert(f"portal_{fp}", cooldown_hours=4):
                send_mail(
                    f"[Stefan] Kunden-Portal ACHTUNG ({len(issues)})",
                    text + ("\n\nReparaturen:\n" + "\n".join(f"- {r}" for r in repairs) if repairs else ""),
                    secrets,
                )
                record_alert(f"portal_{fp}")
            else:
                print("Mail unterdrückt (Alert-Schrank)")

        return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())

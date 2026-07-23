#!/usr/bin/env python3
"""
Route-/DNS-Watchdog (Stefan/Nils): erkennt abgerissene Verknüpfungen.

Schränke: flock, Alert-Cooldown 4h, DNS-Repair max 2/h, snack-api Restart max 2/h.
Cron: */15 (10–15 Min Takt, kein Sekunden-Polling).
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
BERLIN = ZoneInfo("Europe/Berlin")
AGENCY = "digitalehandwerkskunst.de"
ROUTES = (
    ("/api/health", True),
    ("/agency-setup", False),
    ("/nils", False),
    ("/n8n/", False),
    ("/voice-demo/api/health", True),
)


def _backend() -> Path:
    for p in (Path("/root/app/backend"), ROOT / "app" / "backend"):
        if p.is_dir():
            return p
    return ROOT / "app" / "backend"


sys.path.insert(0, str(_backend()))
sys.path.insert(0, str(ROOT))

try:
    from watchdog_cabinets import can_alert, can_repair, fingerprint, flock, record_alert, record_repair
except ImportError:
    # Fallback ohne Schränke (sollte auf Server nicht passieren)
    from contextlib import contextmanager

    @contextmanager
    def flock(name, blocking=False):
        yield True

    def can_alert(*a, **k):
        return True

    def record_alert(*a, **k):
        pass

    def can_repair(*a, **k):
        return True

    def record_repair(*a, **k):
        pass

    def fingerprint(parts):
        return "fp"


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


def _ssl_ctx():
    import ssl

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def resolve_public(host: str) -> str | None:
    try:
        return socket.gethostbyname(host)
    except OSError:
        return None


def http_ok(ip: str, path: str, *, want_json: bool = False) -> tuple[bool, str]:
    url = f"https://{ip}{path}"
    req = urllib.request.Request(url, headers={"Host": AGENCY}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15, context=_ssl_ctx()) as resp:
            body = resp.read().decode("utf-8", "replace")[:120]
            code = resp.status
            ok = 200 <= code < 400
            if want_json and ok:
                ok = "ok" in body.lower() or "status" in body.lower() or body.strip().startswith("{")
            return ok, f"HTTP {code}"
    except urllib.error.HTTPError as e:
        if e.code in (401, 404) and path.startswith("/n8n"):
            return True, f"HTTP {e.code} (n8n erreichbar)"
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)[:100]


def check_local_ports() -> list[dict]:
    out = []
    for port, name in ((5678, "n8n"), (8090, "voice")):
        code = subprocess.getoutput(
            f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:{port}/ 2>/dev/null || echo 000"
        ).strip()
        ok = code in ("200", "301", "302", "401", "404")
        if name == "voice":
            code2 = subprocess.getoutput(
                "curl -sf http://127.0.0.1:8090/api/health >/dev/null && echo 200 || echo 000"
            ).strip()
            ok = code2 == "200"
            code = code2
        out.append({"id": f"local_{name}", "ok": ok, "detail": f"port {port} -> {code}"})
    return out


def try_repair_dns(expected_ip: str, secrets: dict) -> dict | None:
    if not secrets.get("IONOS_API_PREFIX"):
        return None
    try:
        from integrations.ionos_dns import point_domain_to_ip
    except ImportError:
        try:
            from app.backend.integrations.ionos_dns import point_domain_to_ip  # type: ignore
        except ImportError:
            return {"ok": False, "error": "ionos_dns Modul fehlt"}
    return point_domain_to_ip(AGENCY, expected_ip, secrets=secrets)


def try_restart_snack() -> bool:
    if not Path("/etc/systemd/system/snack-api.service").is_file() and not Path(
        "/lib/systemd/system/snack-api.service"
    ).is_file():
        # may still exist as unit
        pass
    r = subprocess.run(["systemctl", "restart", "snack-api"], capture_output=True, text=True, timeout=60)
    return r.returncode == 0


def send_alert(subject: str, text: str, secrets: dict) -> None:
    for k, v in secrets.items():
        os.environ.setdefault(k, v)
    try:
        from agency_mail import send_html_email
    except ImportError:
        print("agency_mail fehlt, keine Mail")
        return
    to = (secrets.get("AGENCY_OWNER_EMAIL") or secrets.get("AGENCY_SMTP_USER") or "").strip()
    if not to:
        return
    html = f"<pre style='font-family:system-ui'>{text.replace('<','&lt;')}</pre>"
    send_html_email(to=to, subject=subject, html=html, text=text)


def main() -> int:
    dry = "--dry-run" in sys.argv
    force_mail = "--mail" in sys.argv

    with flock("route_watchdog", blocking=False) as got:
        if not got:
            print("skip: route_watchdog flock belegt")
            return 0

        secrets = _secrets()
        expected = (secrets.get("WEB_HOST") or "").strip()
        now = datetime.now(BERLIN).strftime("%Y-%m-%d %H:%M %Z")
        issues: list[str] = []
        repairs: list[str] = []

        public_ip = resolve_public(AGENCY)
        print(f"DNS {AGENCY} -> {public_ip} (erwartet {expected})")

        if not expected:
            issues.append("WEB_HOST fehlt in Secrets")
        elif public_ip and public_ip != expected:
            issues.append(f"DNS-Mismatch: oeffentlich {public_ip}, Soll {expected}")
            if not dry:
                if can_repair("dns_ionos", max_per_hour=2):
                    result = try_repair_dns(expected, secrets)
                    if result and result.get("ok"):
                        record_repair("dns_ionos")
                        repairs.append(f"IONOS A-Records -> {expected}")
                    elif result:
                        issues.append(f"Auto-Fix IONOS: {result.get('error')}")
                    else:
                        issues.append("Auto-Fix nicht moeglich (IONOS Keys fehlen)")
                else:
                    issues.append("Schrank: DNS-Repair-Budget leer (max 2/h)")

        target = expected or public_ip or "127.0.0.1"
        api_fail = False
        for path, want_json in ROUTES:
            ok, detail = http_ok(target, path, want_json=want_json)
            mark = "OK" if ok else "FAIL"
            print(f"  [{mark}] {path}: {detail}")
            if not ok:
                issues.append(f"Route {path} auf {target}: {detail}")
                if path == "/api/health":
                    api_fail = True

        if api_fail and not dry:
            # Restart nur wenn wir auf dem Web-Host sind
            web = expected
            local_ips = subprocess.getoutput("hostname -I 2>/dev/null || true").split()
            if web and web in local_ips:
                if can_repair("snack_api_restart", max_per_hour=2):
                    if try_restart_snack():
                        record_repair("snack_api_restart")
                        repairs.append("snack-api restart (api/health rot)")
                    else:
                        issues.append("snack-api restart fehlgeschlagen")
                else:
                    issues.append("Schrank: snack-api Restart-Budget leer")

        for c in check_local_ports():
            print(f"  [{'OK' if c['ok'] else 'FAIL'}] {c['id']}: {c['detail']}")
            if not c["ok"]:
                issues.append(f"{c['id']}: {c['detail']}")

        report = [
            f"Route-Watchdog {now}",
            f"DNS {AGENCY} = {public_ip}",
            f"WEB_HOST = {expected}",
            "",
            "Probleme:" if issues else "Alles OK.",
            *[f"- {i}" for i in issues],
            "",
            "Reparaturen:" if repairs else "",
            *[f"- {r}" for r in repairs],
        ]
        text = "\n".join(x for x in report if x is not None)
        print(text)

        log = Path("/var/log/route-watchdog.log")
        try:
            with open(log, "a", encoding="utf-8") as f:
                f.write(f"\n===== {now} =====\n{text}\n")
        except OSError:
            pass

        if (issues or repairs) and not dry:
            fp = fingerprint(issues + repairs)
            if can_alert(f"route_{fp}", cooldown_hours=4) or force_mail:
                status = "REPARIERT" if repairs and not issues else ("ACHTUNG" if issues else "OK")
                send_alert(f"[Stefan] Route-Watchdog {status}", text, secrets)
                record_alert(f"route_{fp}")
            else:
                print("Mail unterdrueckt (Alert-Schrank 4h)")
        elif force_mail and not dry:
            send_alert("[Stefan] Route-Watchdog OK", text, secrets)

        return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Stefan Morgen-Digest: Status beider Server + Priorität an Christian.

Läuft auf auto-01neu per Cron (Europa/Berlin 07:00).
Kann lokal mit SSH/Secrets getestet werden.

  python scripts/stefan_morning_digest.py           # senden
  python scripts/stefan_morning_digest.py --dry-run # nur printen
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
BERLIN = ZoneInfo("Europe/Berlin")


def _load_secrets() -> dict[str, str]:
    out: dict[str, str] = {}
    for path in (
        Path("/root/app/deploy.secrets.local"),
        ROOT / "deploy.secrets.local",
    ):
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


def _http(url: str, *, host: str | None = None, timeout: int = 12) -> tuple[bool, str]:
    headers = {}
    if host:
        headers["Host"] = host
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
            body = resp.read().decode("utf-8", "replace")[:200]
            return True, f"HTTP {resp.status} {body[:80]}"
    except Exception as e:
        return False, str(e)[:120]


def _ssl_ctx():
    import ssl

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _sh(cmd: str, timeout: int = 15) -> str:
    try:
        r = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return ((r.stdout or "") + (r.stderr or "")).strip()[:300]
    except Exception as e:
        return str(e)[:120]


def _read_priority() -> str:
    for path in (
        Path("/root/app/docs/memory/CURRENT.md"),
        ROOT / "docs" / "memory" / "CURRENT.md",
    ):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        # erste sinnvolle Zeile unter ## Jetzt
        lines = text.splitlines()
        grab = False
        buf: list[str] = []
        for line in lines:
            if line.strip().startswith("## Jetzt"):
                grab = True
                continue
            if grab:
                if line.startswith("## "):
                    break
                if line.strip():
                    buf.append(line.strip())
                if len(buf) >= 3:
                    break
        if buf:
            return " ".join(buf)[:400]
    return "Keine CURRENT.md — Priorität manuell setzen."


def collect(secrets: dict[str, str]) -> dict:
    import socket

    web = secrets.get("WEB_HOST") or "127.0.0.1"
    auto = secrets.get("AUTO_HOST") or "127.0.0.1"
    host = "digitalehandwerkskunst.de"

    checks: list[dict] = []

    # Öffentliches DNS vs WEB_HOST (Migration-Falle)
    try:
        public_ip = socket.gethostbyname(host)
    except OSError:
        public_ip = None
    dns_ok = bool(public_ip and web and public_ip == web)
    checks.append(
        {
            "id": "dns_public",
            "ok": dns_ok,
            "detail": f"{host} → {public_ip or '?'} (Soll {web})",
        }
    )

    # Web via IP + Host-Header (DNS kann noch alt sein)
    ok, detail = _http(f"https://{web}/api/health", host=host)
    checks.append({"id": "web_api", "ok": ok, "detail": detail})

    ok, detail = _http(f"https://{web}/nils", host=host)
    checks.append({"id": "web_nils", "ok": ok, "detail": detail})

    ok, detail = _http(f"http://127.0.0.1:5678/", host=None)
    # n8n root may 404 — treat 2xx/3xx/401/404 as up
    n8n_up = ok or "404" in detail or "401" in detail or "HTTP 2" in detail or "HTTP 3" in detail
    if not ok:
        # urllib may fail on 404
        code = _sh("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5678/ || echo 000")
        n8n_up = code.strip() in ("200", "301", "302", "401", "404")
        detail = f"curl {code.strip()}"
    checks.append({"id": "auto_n8n", "ok": n8n_up, "detail": detail})

    ok, detail = _http("http://127.0.0.1:8090/api/health")
    checks.append({"id": "auto_voice", "ok": ok, "detail": detail})

    # Disk / mem on this host (auto)
    mem = _sh("free -h | awk '/Mem:/ {print $3\"/\"$2}'")
    disk = _sh("df -h / | awk 'NR==2 {print $3\"/\"$2\" (\"$5\")\"}'")
    load = _sh("cut -d' ' -f1-3 /proc/loadavg")

    # Watchdog / akquise log tails
    wd = _sh("tail -3 /var/log/nightly-watchdog.log 2>/dev/null || echo '(kein Log)'")
    akq = _sh("tail -2 /var/log/akquise.log 2>/dev/null || echo '(kein Log)'")

    bad = [c for c in checks if not c["ok"]]
    return {
        "when": datetime.now(BERLIN).strftime("%Y-%m-%d %H:%M %Z"),
        "web_host": web,
        "auto_host": auto,
        "checks": checks,
        "all_ok": len(bad) == 0,
        "bad": bad,
        "mem": mem,
        "disk": disk,
        "load": load,
        "watchdog_tail": wd,
        "akquise_tail": akq,
        "priority": _read_priority(),
    }


def render(data: dict) -> tuple[str, str, str]:
    status = "OK" if data["all_ok"] else "ACHTUNG"
    subject = f"[Stefan] Morgen {status} · {data['when'][:10]}"

    lines = [
        f"Stefan – Morgen-Digest ({data['when']})",
        "",
        f"Priorität (CURRENT): {data['priority']}",
        "",
        "Checks:",
    ]
    for c in data["checks"]:
        mark = "OK" if c["ok"] else "FAIL"
        lines.append(f"  [{mark}] {c['id']}: {c['detail']}")
    dns = next((c for c in data["checks"] if c["id"] == "dns_public"), None)
    if dns and not dns["ok"]:
        lines += [
            "",
            "DNS-MISMATCH: Browser trifft alten Server. Sofort:",
            f"  https://{data['web_host']}/agency-setup",
            "  Oder A-Record @/www bei IONOS auf WEB_HOST setzen.",
        ]    lines += [
        "",
        f"Auto RAM: {data['mem']} · Disk: {data['disk']} · Load: {data['load']}",
        "",
        "Watchdog (letzte Zeilen):",
        data["watchdog_tail"],
        "",
        "Akquise (letzte Zeilen):",
        data["akquise_tail"],
        "",
        "web=" + data["web_host"] + " · auto=" + data["auto_host"],
        "",
        "— Stefan",
    ]
    text = "\n".join(lines)

    rows = "".join(
        f"<tr><td style='padding:4px 8px;'>{'✅' if c['ok'] else '❌'} {c['id']}</td>"
        f"<td style='padding:4px 8px;color:#555;font-size:13px;'>{_esc(c['detail'])}</td></tr>"
        for c in data["checks"]
    )
    html = f"""<!DOCTYPE html><html><body style="font-family:system-ui,sans-serif;color:#1a1a1a;max-width:640px;">
<p style="font-size:18px;margin:0 0 8px;"><strong>Stefan</strong> · Morgen-Digest · {status}</p>
<p style="color:#666;margin:0 0 16px;">{_esc(data['when'])}</p>
<p style="background:#f5f0e8;border-left:4px solid #C9A84C;padding:12px;"><strong>Priorität</strong><br>{_esc(data['priority'])}</p>
<table style="border-collapse:collapse;width:100%;margin:16px 0;">{rows}</table>
<p style="font-size:13px;color:#666;">Auto RAM {_esc(data['mem'])} · Disk {_esc(data['disk'])} · Load {_esc(data['load'])}</p>
<pre style="font-size:11px;background:#111;color:#ccc;padding:10px;overflow:auto;">{_esc(data['watchdog_tail'])}</pre>
<p style="font-size:12px;color:#999;">web {_esc(data['web_host'])} · auto {_esc(data['auto_host'])}</p>
</body></html>"""
    return subject, html, text


def _esc(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def send_mail(subject: str, html: str, text: str, secrets: dict[str, str]) -> None:
    backend = Path("/root/app/backend")
    paths = [str(backend), str(ROOT / "app" / "backend"), str(ROOT), "/root/app"]
    for p in paths:
        if p not in sys.path:
            sys.path.insert(0, p)

    for k, v in secrets.items():
        os.environ.setdefault(k, v)

    # agency_mail reads deploy.secrets.local via agency_mail._read_secrets
    from agency_mail import send_html_email

    to = (
        secrets.get("AGENCY_OWNER_EMAIL")
        or os.getenv("AGENCY_OWNER_EMAIL")
        or secrets.get("AGENCY_SMTP_USER")
        or ""
    ).strip()
    if not to:
        raise RuntimeError("AGENCY_OWNER_EMAIL fehlt")
    send_html_email(to=to, subject=subject, html=html, text=text)


def main() -> int:
    dry = "--dry-run" in sys.argv
    secrets = _load_secrets()
    data = collect(secrets)
    subject, html, text = render(data)
    print(text)
    log_path = Path("/var/log/stefan-digest.log")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n===== {data['when']} =====\n{text}\n")
    except OSError:
        pass

    if dry:
        print("\n(dry-run, keine Mail)")
        return 0 if data["all_ok"] else 1

    try:
        send_mail(subject, html, text, secrets)
        print(f"\nMail gesendet.")
    except Exception as e:
        print(f"\nMail FEHLER: {e}")
        return 2
    return 0 if data["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

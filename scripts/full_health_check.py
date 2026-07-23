#!/usr/bin/env python3
"""Full post-cutover health check (no secrets printed)."""
from __future__ import annotations

import json
import re
import socket
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agency_config import _read_file_secrets, ssh_connect
import paramiko

DOMAIN = "digitalehandwerkskunst.de"
EXPECTED = "167.233.150.230"
OLD = "204.168.170.97"
HOSTS = [
    DOMAIN,
    f"www.{DOMAIN}",
    f"cal.{DOMAIN}",
    f"yassine.{DOMAIN}",
    f"muster.{DOMAIN}",
    f"voice.{DOMAIN}",
]
ROUTES = [
    ("/", False),
    ("/api/health", True),
    ("/agency-setup", False),
    ("/agency-keys", False),
    ("/nils", False),
    ("/n8n/", False),
    ("/voice-demo/api/health", True),
]


def ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def resolve(name: str, dns: str | None = None) -> str:
    if dns:
        try:
            out = subprocess.check_output(
                ["nslookup", name, dns],
                text=True,
                stderr=subprocess.STDOUT,
                timeout=15,
                encoding="utf-8",
                errors="replace",
            )
            # Windows: after "Name: …" the following Address is the answer
            lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
            answer = None
            for i, ln in enumerate(lines):
                if ln.lower().startswith("name:") and name.lower() in ln.lower():
                    for j in range(i + 1, min(i + 4, len(lines))):
                        m = re.match(r"Address(?:es)?:\s*(.+)$", lines[j], re.I)
                        if m:
                            cand = m.group(1).strip()
                            if cand != dns and not cand.endswith(".8.8") and ":" not in cand:
                                answer = cand
                    break
            if not answer:
                # fallback: last IPv4 that is not the resolver
                ips = re.findall(r"\b(\d+\.\d+\.\d+\.\d+)\b", out)
                ips = [ip for ip in ips if ip != dns]
                answer = ips[-1] if ips else "?"
            return answer or "?"
        except Exception as e:
            return f"err:{e}"
    try:
        return socket.gethostbyname(name)
    except OSError:
        return "?"


def http(url: str, host: str | None = None) -> tuple[bool, str]:
    headers = {}
    if host:
        headers["Host"] = host
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20, context=ssl_ctx()) as resp:
            code = resp.status
            ok = 200 <= code < 400
            return ok, f"HTTP {code}"
    except urllib.error.HTTPError as e:
        if e.code in (401, 404) and "/n8n" in url:
            return True, f"HTTP {e.code} (n8n up)"
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)[:100]


def remote_checks():
    results = []
    web = paramiko.SSHClient()
    ssh_connect(web, role="web")
    _, o, _ = web.exec_command(
        "systemctl is-active snack-api; curl -sf http://127.0.0.1:8000/api/health; "
        "getent hosts digitalehandwerkskunst.de | awk '{print $1}'; "
        "df -h / | awk 'NR==2{print $5}'; free -h | awk '/Mem:/{print $3\"/\"$2}'",
        timeout=30,
    )
    text = o.read().decode("utf-8", "replace").strip()
    web.close()
    results.append(("web_ssh", True, text.replace("\n", " | ")[:220]))

    auto = paramiko.SSHClient()
    ssh_connect(auto, role="auto")
    _, o, _ = auto.exec_command(
        "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5678/; "
        "curl -sf http://127.0.0.1:8090/api/health >/dev/null && echo voice_ok || echo voice_fail; "
        "crontab -l 2>/dev/null | grep -E 'route_watchdog|stefan' || true; "
        "df -h / | awk 'NR==2{print $5}'; free -h | awk '/Mem:/{print $3\"/\"$2}'",
        timeout=30,
    )
    text = o.read().decode("utf-8", "replace").strip()
    auto.close()
    results.append(("auto_ssh", True, text.replace("\n", " | ")[:250]))
    return results


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    sec = _read_file_secrets()
    web_host = sec.get("WEB_HOST") or EXPECTED

    print("=== DNS (8.8.8.8 + 1.1.1.1) ===")
    dns_ok = True
    for h in HOSTS:
        g = resolve(h, "8.8.8.8")
        c = resolve(h, "1.1.1.1")
        ok = g == EXPECTED and c == EXPECTED
        dns_ok = dns_ok and ok
        print(f"  [{'OK' if ok else 'FAIL'}] {h}  google={g}  cloudflare={c}")

    print(f"\n=== HTTPS am neuen Server ({web_host}) ===")
    routes_ok = True
    for path, _ in ROUTES:
        ok, detail = http(f"https://{web_host}{path}", host=DOMAIN)
        if not ok and path.startswith("/n8n"):
            ok = "401" in detail or "404" in detail
        routes_ok = routes_ok and ok
        print(f"  [{'OK' if ok else 'FAIL'}] {path}: {detail}")

    print("\n=== Alter Server (Helsinki, sollte bald weg) ===")
    ok_old, d_old = http(f"https://{OLD}/api/health", host=DOMAIN)
    print(f"  [{'WARN' if ok_old else 'OK offline'}] old /api/health: {d_old}")

    print("\n=== Server (SSH) ===")
    try:
        for name, ok, detail in remote_checks():
            print(f"  [{'OK' if ok else 'FAIL'}] {name}: {detail}")
    except Exception as e:
        print(f"  [FAIL] ssh: {e}")

    print("\n=== IONOS Zone (API) ===")
    try:
        import urllib.request as u

        keys = dict(sec)
        for line in (ROOT / "ionos-api.local.txt").read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            keys[k.strip()] = v.strip()
        key = f"{keys['IONOS_API_PREFIX']}.{keys['IONOS_API_SECRET']}"
        req = u.Request(
            "https://api.hosting.ionos.com/dns/v1/zones",
            headers={"X-API-Key": key, "Accept": "application/json"},
        )
        with u.urlopen(req, timeout=30) as resp:
            zones = json.loads(resp.read())
        zid = next(z["id"] for z in zones if z.get("name") == DOMAIN)
        req = u.Request(
            f"https://api.hosting.ionos.com/dns/v1/zones/{zid}",
            headers={"X-API-Key": key, "Accept": "application/json"},
        )
        with u.urlopen(req, timeout=30) as resp:
            zone = json.loads(resp.read())
        ionos_ok = True
        for r in zone.get("records") or []:
            if (r.get("type") or "").upper() != "A":
                continue
            ok = r.get("content") == EXPECTED
            ionos_ok = ionos_ok and ok
            print(f"  [{'OK' if ok else 'FAIL'}] A {r.get('name')} = {r.get('content')}")
    except Exception as e:
        ionos_ok = False
        print(f"  [FAIL] {e}")

    print("\n=== FAZIT ===")
    all_ok = dns_ok and routes_ok and ionos_ok
    if all_ok:
        print("ALLES GRUEN auf dem neuen Server.")
        if ok_old:
            print("Hinweis: Alter Helsinki-Server antwortet noch – bald kuendigen.")
        print("Browser: Cache leeren oder Privates Fenster, falls noch alte Seite.")
    else:
        print("ES GIBT ABWEICHUNGEN (siehe FAIL oben)")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

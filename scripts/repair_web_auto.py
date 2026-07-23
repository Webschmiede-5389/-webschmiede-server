#!/usr/bin/env python3
"""Repair web-01neu + auto-01neu linkages and verify proxies."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agency_config import ssh_connect, target_secrets


def _stdout_safe():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def run(c, cmd, t=120):
    print(f"$ {cmd[:100]}")
    _, o, e = c.exec_command(cmd, timeout=t)
    code = o.channel.recv_exit_status()
    text = (o.read() + e.read()).decode("utf-8", "replace")
    if text.strip():
        print(text[-2000:] if len(text) > 2000 else text)
    return code, text


def main():
    _stdout_safe()
    web_ip = target_secrets("web")["SERVER_HOST"]
    auto_ip = target_secrets("auto")["SERVER_HOST"]

    # --- WEB ---
    web = paramiko.SSHClient()
    ssh_connect(web, role="web")
    print("\n=== WEB REPAIRS ===")

    # Remove typo site + default conflict
    run(
        web,
        "rm -f /etc/nginx/sites-enabled/default "
        "/etc/nginx/sites-enabled/snackhouse-yacine.de "
        "/etc/nginx/sites-available/snackhouse-yacine.de 2>/dev/null; true",
    )

    # Ensure n8n + voice proxy point to auto
    run(
        web,
        f"grep -rl 'proxy_pass' /etc/nginx/sites-available /etc/nginx/sites-enabled 2>/dev/null | "
        f"xargs -r sed -i "
        f"-e 's|http://[0-9.]\\+:5678|http://{auto_ip}:5678|g' "
        f"-e 's|http://[0-9.]\\+:8090|http://{auto_ip}:8090|g'",
    )
    run(web, "nginx -t && systemctl reload nginx")

    # Cal.com: check why unhealthy
    run(web, "docker compose -f /opt/calcom/docker-compose.yml ps")
    run(web, "docker logs calcom-calcom-1 --tail 30 2>&1")
    run(web, "curl -sf -o /dev/null -w 'cal:%{http_code}\\n' http://127.0.0.1:3000/ || echo cal_fail")

    # Local proxy smoke via Host header
    for path, label in [
        ("/api/health", "api"),
        ("/n8n/", "n8n"),
        ("/voice-demo/api/health", "voice"),
        ("/nils", "nils"),
    ]:
        run(
            web,
            f'curl -sk -o /dev/null -w "{label}:%{{http_code}}\\n" '
            f'-H "Host: digitalehandwerkskunst.de" https://127.0.0.1{path}',
        )

    # Direct reachability to auto
    run(web, f"curl -sf -o /dev/null -w 'auto-n8n:%{{http_code}}\\n' http://{auto_ip}:5678/ || echo auto-n8n-fail")
    run(web, f"curl -sf -o /dev/null -w 'auto-voice:%{{http_code}}\\n' http://{auto_ip}:8090/api/health || echo auto-voice-fail")

    # Subdomain sites
    for host in ("yassine.digitalehandwerkskunst.de", "muster.digitalehandwerkskunst.de", "cal.digitalehandwerkskunst.de"):
        run(
            web,
            f'curl -sk -o /dev/null -w "{host}:%{{http_code}}\\n" -H "Host: {host}" https://127.0.0.1/',
        )

    web.close()

    # --- AUTO ---
    auto = paramiko.SSHClient()
    ssh_connect(auto, role="auto")
    print("\n=== AUTO REPAIRS ===")

    # UFW: ensure web can reach n8n+voice; drop stale old web if wanted (keep both ok)
    run(auto, f"ufw allow from {web_ip} to any port 5678 proto tcp")
    run(auto, f"ufw allow from {web_ip} to any port 8090 proto tcp")
    run(auto, "systemctl is-active n8n; systemctl enable n8n 2>/dev/null; true")

    # Cron scripts exist?
    run(
        auto,
        "for s in run_followups.sh nightly_watchdog.sh resource_watchdog.sh backup_agency.sh "
        "hetzner_buyer_cron.sh akquise_nightly.sh; do "
        "test -x /root/app/scripts/$s && echo OK $s || echo MISSING $s; done",
    )
    run(auto, "ls /root/app/scripts/*.py 2>/dev/null | head -20")

    # Voice stack healthy
    run(auto, "curl -sf http://127.0.0.1:8090/api/health")
    run(auto, "docker compose -f /root/app/infra/voice-demo/docker-compose.yml ps")

    # n8n restart if needed
    run(auto, "systemctl restart n8n; sleep 3; systemctl is-active n8n; curl -sf -o /dev/null -w 'n8n:%{http_code}\\n' http://127.0.0.1:5678/")

    auto.close()
    print("\nDone repairs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

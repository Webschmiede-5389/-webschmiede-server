#!/usr/bin/env python3
"""Install Route-/DNS-Watchdog on auto-01neu (every 15 min) + nginx IP-Zugang on web."""
from __future__ import annotations

import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agency_config import ssh_connect, _read_file_secrets


def normalize_lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def run(c, cmd, t=120):
    print(f"$ {cmd[:120]}")
    _, o, e = c.exec_command(cmd, timeout=t)
    code = o.channel.recv_exit_status()
    text = (o.read() + e.read()).decode("utf-8", "replace")
    if text.strip():
        print(text[-2000:] if len(text) > 2000 else text)
    return code, text


def put(sftp, local: Path, remote: str, shell: bool = False):
    data = local.read_bytes()
    data = normalize_lf(data) if shell else data.replace(b"\r\n", b"\n")
    with sftp.file(remote, "wb") as f:
        f.write(data)
    print(f"put {remote}")


def merge_secrets(c, sftp, local: dict):
    remote = "/root/app/deploy.secrets.local"
    existing: dict[str, str] = {}
    try:
        with sftp.file(remote, "r") as f:
            for line in f.read().decode("utf-8", "replace").splitlines():
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, v = s.split("=", 1)
                existing[k.strip()] = v.strip()
    except OSError:
        pass
    for k in (
        "WEB_HOST",
        "AUTO_HOST",
        "AGENCY_OWNER_EMAIL",
        "AGENCY_SMTP_HOST",
        "AGENCY_SMTP_PORT",
        "AGENCY_SMTP_USER",
        "AGENCY_SMTP_PASS",
        "AGENCY_SMTP_FROM",
        "IONOS_API_PREFIX",
        "IONOS_API_SECRET",
    ):
        if local.get(k):
            existing[k] = local[k]
    data = ("\n".join(f"{k}={v}" for k, v in existing.items()) + "\n").encode("utf-8")
    with sftp.file(remote, "w") as f:
        f.write(data)
    print("secrets merged (values not printed)")


NGINX_IP = """# Default: Agency Setup per Server-IP (wenn DNS noch auf altem Server zeigt)
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    return 301 https://$host$request_uri;
}
server {
    listen 443 ssl default_server;
    listen [::]:443 ssl default_server;
    server_name _;

    ssl_certificate     /etc/letsencrypt/live/digitalehandwerkskunst.de/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/digitalehandwerkskunst.de/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    root /var/www/snackhouse-mechernich;
    index index.html;

    location = /agency-setup {
        root /var/www/snackhouse-mechernich;
        try_files /agency-setup.html =404;
    }
    location = /agency-setup.html {
        root /var/www/snackhouse-mechernich;
        try_files /agency-setup.html =404;
    }
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host digitalehandwerkskunst.de;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 30;
    }
    location / {
        try_files $uri $uri/ =404;
    }
}
"""


def setup_web_ip_access(local: dict) -> None:
    web = paramiko.SSHClient()
    ssh_connect(web, role="web")
    sftp = web.open_sftp()
    run(web, "mkdir -p /root/app/static /root/app/backend/integrations /etc/nginx/sites-available")

    put(sftp, ROOT / "app/static/agency-setup.html", "/root/app/static/agency-setup.html")
    put(sftp, ROOT / "app/backend/integrations/ionos_dns.py", "/root/app/backend/integrations/ionos_dns.py")
    put(sftp, ROOT / "app/backend/agency_secrets.py", "/root/app/backend/agency_secrets.py")

    # Sync HTML to nginx roots (same as deploy)
    for dest in (
        "/var/www/snackhouse-mechernich/agency-setup.html",
        "/var/www/digitalehandwerkskunst/agency-setup.html",
    ):
        put(sftp, ROOT / "app/static/agency-setup.html", dest)

    conf = normalize_lf(NGINX_IP.encode("utf-8"))
    with sftp.file("/etc/nginx/sites-available/00-ip-default", "wb") as f:
        f.write(conf)
    # disable stock default if present
    run(web, "rm -f /etc/nginx/sites-enabled/default")
    run(web, "ln -sfn /etc/nginx/sites-available/00-ip-default /etc/nginx/sites-enabled/00-ip-default")
    # drop default_server from other listen lines if they conflict (snack-house sometimes)
    run(
        web,
        "sed -i 's/ listen 80 default_server;/ listen 80;/; s/ listen \\[::\\]:80 default_server;/ listen [::]:80;/' "
        "/etc/nginx/sites-enabled/* 2>/dev/null; true",
    )
    code, _ = run(web, "nginx -t && systemctl reload nginx")
    if code != 0:
        print("WARN nginx reload failed")
    run(web, "systemctl restart snack-api || true")
    # smoke bare IP
    ip = local.get("WEB_HOST") or "127.0.0.1"
    run(
        web,
        f"curl -sk -o /dev/null -w 'bare_setup:%{{http_code}}\\n' https://{ip}/agency-setup; "
        f"curl -sk -o /dev/null -w 'bare_api:%{{http_code}}\\n' https://{ip}/api/health",
    )
    sftp.close()
    web.close()
    print(f"IP-Zugang: https://{ip}/agency-setup")


def setup_auto(local: dict) -> None:
    c = paramiko.SSHClient()
    ssh_connect(c, role="auto")
    sftp = c.open_sftp()
    run(c, "mkdir -p /root/app/scripts /root/app/backend/integrations")
    put(sftp, ROOT / "scripts/route_watchdog.py", "/root/app/scripts/route_watchdog.py")
    put(sftp, ROOT / "scripts/route_watchdog.sh", "/root/app/scripts/route_watchdog.sh", shell=True)
    put(sftp, ROOT / "app/backend/integrations/ionos_dns.py", "/root/app/backend/integrations/ionos_dns.py")
    put(sftp, ROOT / "app/backend/agency_mail.py", "/root/app/backend/agency_mail.py")
    # empty __init__ if missing
    run(c, "touch /root/app/backend/integrations/__init__.py /root/app/backend/__init__.py")
    merge_secrets(c, sftp, local)
    sftp.close()

    run(c, "chmod +x /root/app/scripts/route_watchdog.sh")
    run(c, "sed -i 's/\\r$//' /root/app/scripts/route_watchdog.sh")

    # Cron every 15 min
    run(
        c,
        "("
        "crontab -l 2>/dev/null | grep -v route_watchdog; "
        "echo '*/15 * * * * /bin/bash /root/app/scripts/route_watchdog.sh'"
        ") | crontab -",
    )
    run(c, "crontab -l | grep route_watchdog")
    run(c, "/usr/bin/python3 /root/app/scripts/route_watchdog.py --dry-run", t=60)
    c.close()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    local = _read_file_secrets()
    print("=== Web: IP-Zugang agency-setup ===")
    setup_web_ip_access(local)
    print("=== Auto: Route-Watchdog Cron ===")
    setup_auto(local)
    print("FERTIG")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""n8n einrichten: nginx, Workflows importieren, Buchhaltungs-Env."""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import paramiko
from agency_config import load_secrets, ssh_connect

HOST = load_secrets()["SERVER_HOST"]
N8N_DIR = Path(__file__).resolve().parent.parent / "infra" / "n8n"
REMOTE_IMPORT = "/tmp/n8n-workflows"
NGINX_SITE_SNACK = "/etc/nginx/sites-available/snack-house"
NGINX_SITE_AGENCY = "/etc/nginx/sites-available/digitalehandwerkskunst.de"
N8N_ENV = "/opt/n8n/.env"
APP_ENV = "/root/app/backend/.env"

# Agency-Absender (nicht kundenspezifisch)
DEFAULT_FROM = "info@digitalehandwerkskunst.de"

NGINX_N8N = """
    # n8n Automation Hub
    location /n8n/ {
        proxy_pass         http://127.0.0.1:5678/n8n/;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
        chunked_transfer_encoding off;
    }
"""

PRIORITY_WORKFLOWS = [
    "workflow-meta-rechnungen.json",
    "workflow-buchhaltung-monat.json",
    "workflow-new-order-alert.json",
    "workflow-inbox-agent.json",
    "workflow-inbox-digest.json",
    "workflow-monatsreport.json",
]


def run(client, cmd, timeout=120):
    _, out, err = client.exec_command(cmd, timeout=timeout)
    o = out.read().decode("utf-8", errors="replace").strip()
    e = err.read().decode("utf-8", errors="replace").strip()
    return o, e


def read_env_remote(client, path: str) -> dict[str, str]:
    text, _ = run(client, f"cat {path} 2>/dev/null || true")
    env: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def upsert_env_var(client, path: str, key: str, value: str):
    run(
        client,
        f"grep -q '^{key}=' {path} 2>/dev/null && "
        f"sed -i 's|^{key}=.*|{key}={value}|' {path} || "
        f"echo '{key}={value}' >> {path}",
    )


def patch_site_nginx(client, site_path: str):
    nginx, _ = run(client, f"cat {site_path}")
    if "location /n8n/" in nginx:
        nginx = re.sub(
            r"location /n8n/ \{[^}]+\}",
            NGINX_N8N.strip(),
            nginx,
            count=1,
            flags=re.DOTALL,
        )
    else:
        marker = "    location /api/ {"
        if marker not in nginx:
            marker = "    location / {"
        if marker not in nginx:
            raise RuntimeError(f"Kein Einfuegepunkt in {site_path}")
        nginx = nginx.replace(marker, NGINX_N8N + "\n" + marker, 1)
    sftp = client.open_sftp()
    with sftp.open(site_path, "w") as f:
        f.write(nginx)
    sftp.close()


def fix_nginx(client):
    for site in (NGINX_SITE_SNACK, NGINX_SITE_AGENCY):
        if run(client, f"test -f {site} && echo yes || echo no")[0].strip() != "yes":
            continue
        patch_site_nginx(client, site)
        print(f"nginx gepatcht: {site}")
    test, _ = run(client, "nginx -t 2>&1")
    if "successful" not in test:
        raise RuntimeError(f"nginx -t fehlgeschlagen: {test}")
    run(client, "systemctl reload nginx")
    # IP-Anfragen landen auf default_server (snack-house)
    run(client, f"sed -i 's/listen 80;/listen 80 default_server;/' {NGINX_SITE_SNACK}")
    run(client, f"sed -i 's/listen \\[::\\]:80;/listen [::]:80 default_server;/' {NGINX_SITE_SNACK} 2>/dev/null || true")
    run(client, "nginx -t 2>&1 && systemctl reload nginx")
    for url in (
        'curl -s -o /dev/null -w "%{http_code}" http://167.233.211.170/n8n/',
        'curl -s -o /dev/null -w "%{http_code}" -H "Host: digitalehandwerkskunst.de" http://127.0.0.1/n8n/',
    ):
        code, _ = run(client, url)
        print(f"  {url.split()[-1]} -> HTTP {code}")


def upload_workflows(client):
    run(client, f"rm -rf {REMOTE_IMPORT} && mkdir -p {REMOTE_IMPORT}")
    sftp = client.open_sftp()
    count = 0
    for wf in sorted(N8N_DIR.glob("workflow-*.json")):
        raw = json.loads(wf.read_text(encoding="utf-8-sig"))
        raw.setdefault("active", False)
        remote = f"{REMOTE_IMPORT}/{wf.name}"
        with sftp.open(remote, "w") as f:
            f.write(json.dumps(raw, ensure_ascii=False, indent=2))
        count += 1
    sftp.close()
    print(f"Upload: {count} Workflows")


def import_workflows(client):
    cmd = (
        f"export $(grep -v '^#' {N8N_ENV} | xargs) && "
        f"N8N_USER_FOLDER=/opt/n8n/data "
        f"n8n import:workflow --separate --input={REMOTE_IMPORT} 2>&1"
    )
    out, err = run(client, cmd, timeout=180)
    print(out or err)
    if "error" in (out + err).lower() and "imported" not in (out + err).lower():
        # Fallback: einzeln
        for name in PRIORITY_WORKFLOWS:
            cmd1 = (
                f"export $(grep -v '^#' {N8N_ENV} | xargs) && "
                f"N8N_USER_FOLDER=/opt/n8n/data "
                f"n8n import:workflow -i {REMOTE_IMPORT}/{name} 2>&1"
            )
            o, e = run(client, cmd1, timeout=60)
            print(f"  {name}: {(o or e)[:120]}")


def activate_workflows(client):
    py = r"""
import sqlite3, json, subprocess, os
db = '/opt/n8n/data/.n8n/database.sqlite'
conn = sqlite3.connect(db)
rows = conn.execute('SELECT id, name, active FROM workflow_entity').fetchall()
for wid, name, active in rows:
    if not active:
        conn.execute('UPDATE workflow_entity SET active=1 WHERE id=?', (wid,))
        print('activated:', name)
conn.commit()
conn.close()
print('workflows:', len(rows))
"""
    sftp = client.open_sftp()
    with sftp.open("/tmp/n8n_activate.py", "w") as f:
        f.write(py)
    sftp.close()
    out, _ = run(client, "/root/app/venv/bin/python /tmp/n8n_activate.py")
    print(out)
    run(client, "systemctl restart n8n")
    time.sleep(8)
    print("n8n status:", run(client, "systemctl is-active n8n")[0])


def set_agency_n8n_env(client):
    """Nur Agency-weite n8n-Variablen — keine Kunden-Mails."""
    app_env = read_env_remote(client, APP_ENV)
    admin_pw = app_env.get("ADMIN_PASSWORD", "")
    cron = app_env.get("CRON_SECRET", "")

    upsert_env_var(client, N8N_ENV, "AGENCY_FROM_EMAIL", DEFAULT_FROM)
    if admin_pw:
        upsert_env_var(client, N8N_ENV, "ADMIN_PASSWORD", admin_pw)
    if cron:
        upsert_env_var(client, N8N_ENV, "CRON_SECRET", cron)
    run(client, f"sed -i '/^BOOKKEEPER_EMAIL=/d' {N8N_ENV}")

    print(f"AGENCY_FROM_EMAIL -> {DEFAULT_FROM}")
    print("BOOKKEEPER_EMAIL -> entfernt (pro Kunde in kunden/*.json)")


def main():
    client = paramiko.SSHClient()
    ssh_connect(client)
    print("=== 1. nginx /n8n/ ===")
    fix_nginx(client)
    print("\n=== 2. Agency-n8n-Env ===")
    set_agency_n8n_env(client)
    print("\n=== 3. Workflows upload + import ===")
    upload_workflows(client)
    import_workflows(client)
    print("\n=== 4. Workflows aktivieren ===")
    activate_workflows(client)
    client.close()
    print(f"\nFertig. UI: http://{HOST}/n8n/")
    print("Manuell in n8n: SMTP + IMAP Credentials an die E-Mail-Nodes hängen.")
    print("(Meta-Rechnungen brauchen IMAP nur wenn Meta wirklich mailt.)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Install n8n + DB-Backups + nginx proxy on Webschmiede server."""
import os
import secrets
import sys
import time

import paramiko
from agency_config import load_secrets, ssh_connect

HOST = load_secrets()["SERVER_HOST"]
N8N_USER = 'webschmiede'
N8N_DIR = '/opt/n8n'
ENV_FILE = f'{N8N_DIR}/.env'
NGINX_SITE = '/etc/nginx/sites-available/snack-house'

NGINX_EXTRA = r"""
    # Menu uploads (Flask)
    location /uploads/ {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
    }

    # n8n Automation Hub
    location /n8n/ {
        proxy_pass         http://127.0.0.1:5678/;
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

SYSTEMD_UNIT = """[Unit]
Description=n8n workflow automation (Webschmiede)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/n8n
EnvironmentFile=/opt/n8n/.env
ExecStart=/usr/bin/n8n start
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""

BACKUP_SCRIPT = """#!/bin/bash
set -e
BK=/root/app/backups
DB=/root/app/backend/orders.db
mkdir -p "$BK"
STAMP=$(date +%Y%m%d_%H%M)
cp "$DB" "$BK/orders_${STAMP}.db"
find "$BK" -name 'orders_*.db' -mtime +14 -delete
echo "backup ok ${STAMP}"
"""


def connect():
    c = paramiko.SSHClient()
    ssh_connect(c, timeout=20, banner_timeout=20)
    return c


def run(client, cmd, timeout=120):
    _, out, err = client.exec_command(cmd, timeout=timeout)
    o = out.read().decode('utf-8', errors='replace').strip()
    e = err.read().decode('utf-8', errors='replace').strip()
    if o:
        sys.stdout.buffer.write(o.encode('utf-8', errors='replace'))
        sys.stdout.buffer.write(b'\n')
    if e and 'WARNING' not in e.upper() and 'npm warn' not in e.lower():
        print('ERR:', e[:500])
    return o


def main():
    n8n_pass = secrets.token_urlsafe(16)
    enc_key = secrets.token_hex(16)

    client = connect()

    print('=== Node.js prüfen / installieren ===')
    node_v = run(client, 'node -v 2>/dev/null || echo MISSING')
    if 'MISSING' in node_v or not node_v.startswith('v'):
        run(client, 'apt-get update -qq', timeout=180)
        run(client, 'apt-get install -y -qq ca-certificates curl gnupg', timeout=180)
        run(client, 'curl -fsSL https://deb.nodesource.com/setup_20.x | bash -', timeout=180)
        run(client, 'apt-get install -y -qq nodejs', timeout=180)
    run(client, 'node -v && npm -v')

    print('\n=== n8n installieren ===')
    run(client, f'mkdir -p {N8N_DIR} /root/app/backups /root/app/scripts')
    run(client, 'npm install -g n8n@1.97.1 --omit=dev', timeout=600)
    run(client, 'n8n --version')

    env_content = f"""N8N_HOST=0.0.0.0
N8N_PORT=5678
N8N_PROTOCOL=http
N8N_PATH=/n8n/
WEBHOOK_URL=http://{HOST}/n8n/
N8N_EDITOR_BASE_URL=http://{HOST}/n8n/
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER={N8N_USER}
N8N_BASIC_AUTH_PASSWORD={n8n_pass}
N8N_ENCRYPTION_KEY={enc_key}
GENERIC_TIMEZONE=Europe/Berlin
TZ=Europe/Berlin
N8N_SECURE_COOKIE=false
N8N_DIAGNOSTICS_ENABLED=false
N8N_PERSONALIZATION_ENABLED=false
N8N_HIRING_BANNER_ENABLED=false
NODE_OPTIONS=--max-old-space-size=512
N8N_USER_FOLDER={N8N_DIR}/data
"""
    sftp = client.open_sftp()
    with sftp.open(ENV_FILE, 'w') as f:
        f.write(env_content)
    with sftp.open('/etc/systemd/system/n8n.service', 'w') as f:
        f.write(SYSTEMD_UNIT)
    with sftp.open('/root/app/scripts/backup_db.sh', 'w') as f:
        f.write(BACKUP_SCRIPT)
    sftp.close()

    run(client, 'chmod +x /root/app/scripts/backup_db.sh')
    run(client, 'sed -i "s/\\r$//" /root/app/scripts/backup_db.sh')

    print('\n=== nginx: n8n + uploads ===')
    nginx = run(client, f'cat {NGINX_SITE}')
    if 'location /n8n/' not in nginx:
        marker = '    # Backend API Proxy'
        if marker in nginx:
            nginx = nginx.replace(marker, NGINX_EXTRA + '\n' + marker)
        else:
            nginx = nginx.replace('    location /api/ {', NGINX_EXTRA + '\n    location /api/ {')
        sftp = client.open_sftp()
        with sftp.open(NGINX_SITE, 'w') as f:
            f.write(nginx)
        sftp.close()
        run(client, 'nginx -t && systemctl reload nginx')

    print('\n=== systemd n8n ===')
    run(client, 'systemctl daemon-reload')
    run(client, 'systemctl enable n8n')
    run(client, 'systemctl restart n8n', timeout=60)
    time.sleep(8)
    run(client, 'systemctl is-active n8n')
    run(client, 'curl -sf -o /dev/null -w "n8n HTTP:%{http_code}\\n" http://127.0.0.1:5678/ || true')

    print('\n=== Cron: DB-Backup täglich 03:00 ===')
    cron = '0 3 * * * /bin/bash /root/app/scripts/backup_db.sh >> /var/log/snack-backup.log 2>&1'
    run(client, f'(crontab -l 2>/dev/null | grep -v backup_db.sh; echo "{cron}") | crontab -')

    # Save credentials locally for agency (not committed with real pass in git - write to local file)
    cred_path = os.path.join(os.path.dirname(__file__), 'n8n-credentials.local.txt')
    with open(cred_path, 'w', encoding='utf-8') as f:
        f.write(f"n8n URL:      http://{HOST}/n8n/\n")
        f.write(f"n8n User:     {N8N_USER}\n")
        f.write(f"n8n Password: {n8n_pass}\n")
        f.write(f"Encryption:   {enc_key}\n")

    client.close()
    print('\n=== FERTIG ===')
    print(f'URL:  http://{HOST}/n8n/')
    print(f'User: {N8N_USER}')
    print(f'Pass: {n8n_pass}')
    print(f'(auch in {cred_path})')


if __name__ == '__main__':
    main()

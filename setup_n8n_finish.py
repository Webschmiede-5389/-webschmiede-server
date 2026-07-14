"""Finish n8n setup if interrupted (nginx + systemd + cron)."""
import os, sys, time, secrets, paramiko

sys.path.insert(0, os.path.dirname(__file__))
from setup_n8n import (
    HOST, N8N_USER, NGINX_SITE, NGINX_EXTRA, connect, run, BACKUP_SCRIPT, N8N_DIR, ENV_FILE, SYSTEMD_UNIT
)

def main():
    client = connect()
    n8n_pass = secrets.token_urlsafe(16)
    enc_key = secrets.token_hex(16)

    # Check if env exists
    exists = run(client, f'test -f {ENV_FILE} && echo YES || echo NO')
    if 'NO' in exists:
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
        sftp.close()
    else:
        n8n_pass = run(client, f"grep N8N_BASIC_AUTH_PASSWORD= {ENV_FILE} | cut -d= -f2")
        print('Env exists, reusing password from server')

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

    run(client, 'systemctl daemon-reload')
    run(client, 'systemctl enable n8n')
    run(client, 'systemctl restart n8n', timeout=60)
    time.sleep(10)
    run(client, 'systemctl is-active n8n')
    run(client, 'journalctl -u n8n -n 15 --no-pager')
    run(client, 'curl -sf -o /dev/null -w "n8n:%{http_code}\\n" -u webschmiede:pass http://127.0.0.1:5678/ 2>/dev/null || curl -sf -o /dev/null -w "n8n:%{http_code}\\n" http://127.0.0.1:5678/')

    cron = '0 3 * * * /bin/bash /root/app/scripts/backup_db.sh >> /var/log/snack-backup.log 2>&1'
    run(client, f'(crontab -l 2>/dev/null | grep -v backup_db.sh; echo "{cron}") | crontab -')

    cred_path = os.path.join(os.path.dirname(__file__), 'n8n-credentials.local.txt')
    if n8n_pass and 'NO' in exists:
        with open(cred_path, 'w', encoding='utf-8') as f:
            f.write(f"n8n URL:      http://{HOST}/n8n/\n")
            f.write(f"n8n User:     {N8N_USER}\n")
            f.write(f"n8n Password: {n8n_pass}\n")

    client.close()
    print('Done. Open http://167.233.211.170/n8n/')

if __name__ == '__main__':
    main()

"""Jarvis-Bot Secrets auf Server setzen."""
import paramiko
import secrets
from agency_config import ssh_connect

ENV_PATH = '/root/app/backend/.env'

client = paramiko.SSHClient()
ssh_connect(client, timeout=15, banner_timeout=15)

def run(cmd, timeout=20):
    _, out, err = client.exec_command(cmd, timeout=timeout)
    o = out.read().decode('utf-8', errors='replace').strip()
    e = err.read().decode('utf-8', errors='replace').strip()
    if o:
        print(o)
    if e:
        print('ERR:', e[:300])
    return o

secret = secrets.token_hex(24)
run(f'mkdir -p /root/app/kunden /root/app/uploads/menu /root/app/jarvis')

pairs = [
    ('JARVIS_BOT_SECRET', secret),
    ('WHATSAPP_VERIFY_TOKEN', 'webschmiede-verify'),
    ('KUNDEN_DIR', '/root/app/kunden'),
    ('JARVIS_UPLOAD_DIR', '/root/app/uploads/menu'),
]
for key, val in pairs:
    run(f"grep -q '^{key}=' {ENV_PATH} || echo '{key}={val}' >> {ENV_PATH}")

# Nginx: /uploads/ an Flask
run("""grep -q 'location /uploads/' /etc/nginx/sites-enabled/default 2>/dev/null || \\
  sed -i '/location \\/api\\//i\\    location /uploads/ {\\n        proxy_pass http://127.0.0.1:8000;\\n        proxy_set_header Host $host;\\n    }\\n' /etc/nginx/sites-enabled/default 2>/dev/null || true""")
run('nginx -t && systemctl reload nginx')

run('systemctl restart snack-api', timeout=45)
import time
time.sleep(3)
run('systemctl is-active snack-api')
run(f'grep JARVIS_BOT_SECRET {ENV_PATH}')
client.close()
print('\nJarvis env fertig. Secret oben notieren für test_jarvis_bot.py')

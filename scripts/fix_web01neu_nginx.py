#!/usr/bin/env python3
import sys
from pathlib import Path
import paramiko

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agency_config import ssh_connect, target_secrets


def run(c, cmd, t=600):
    print(f"$ {cmd[:95]}")
    _, o, e = c.exec_command(cmd, timeout=t)
    code = o.channel.recv_exit_status()
    text = (o.read() + e.read()).decode("utf-8", "replace")
    if text.strip():
        print(text[-3000:])
    return code


c = paramiko.SSHClient()
ssh_connect(c, role="web")
ip = target_secrets("web")["SERVER_HOST"]

run(c, "grep -rl 'http2' /etc/nginx/sites-enabled /etc/nginx/sites-available | xargs -r sed -i '/http2/d'")
run(c, "grep -rl 'ssl http2' /etc/nginx/sites-enabled /etc/nginx/sites-available | xargs -r sed -i 's/ ssl http2/ ssl/g'")
run(c, "nginx -t")
run(c, "systemctl restart nginx && systemctl is-active nginx")

run(
    c,
    """
cd /root/app
rm -rf venv
python3 -m venv venv
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install -q -r backend/requirements.txt gunicorn
""",
    t=900,
)
run(c, "systemctl restart snack-api && sleep 3 && systemctl is-active snack-api")
run(c, "curl -sf http://127.0.0.1:8000/api/health")
run(c, "cd /opt/calcom && docker compose up -d 2>&1 | tail -5")
run(
    c,
    'curl -sk -o /dev/null -w "api:%{http_code} " -H "Host: digitalehandwerkskunst.de" https://127.0.0.1/api/health; '
    'curl -sk -o /dev/null -w "voice:%{http_code}" -H "Host: digitalehandwerkskunst.de" https://127.0.0.1/voice-demo/api/health',
)
c.close()
print(f"\nOK web-01neu {ip}")

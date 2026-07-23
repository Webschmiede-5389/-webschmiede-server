#!/usr/bin/env python3
"""Gunicorn Timeout hochsetzen (Telegram+Ollama brauchen >30s)."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agency_config import ssh_connect
import paramiko

UNIT = """[Unit]
Description=Snack House Yassine – Order API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/app/backend
EnvironmentFile=/root/app/backend/.env
ExecStart=/root/app/venv/bin/gunicorn -w 3 -b 127.0.0.1:8000 --timeout 120 --graceful-timeout 30 main:app
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""


def main() -> int:
    c = paramiko.SSHClient()
    ssh_connect(c, timeout=25, banner_timeout=25, role="web")
    sftp = c.open_sftp()
    with sftp.file("/etc/systemd/system/snack-api.service", "w") as f:
        f.write(UNIT)
    sftp.close()
    _, o, e = c.exec_command(
        "systemctl daemon-reload && systemctl restart snack-api && sleep 2 && "
        "systemctl is-active snack-api && systemctl cat snack-api | grep ExecStart",
        timeout=60,
    )
    print(o.read().decode(errors="replace"))
    print(e.read().decode(errors="replace")[:500])
    # warm ollama
    _, o2, _ = c.exec_command(
        """python3 - <<'PY'
import os, requests
url=os.environ.get('OLLAMA_URL') or open('/root/app/backend/.env').read()
# parse
u=''
for line in open('/root/app/backend/.env'):
    if line.startswith('OLLAMA_URL='):
        u=line.split('=',1)[1].strip()
model='qwen2.5:14b'
for line in open('/root/app/backend/.env'):
    if line.startswith('OLLAMA_MODEL='):
        model=line.split('=',1)[1].strip() or model
r=requests.post(u.rstrip('/')+'/api/chat', json={
  'model': model, 'stream': False, 'keep_alive': '30m',
  'messages':[{'role':'user','content':'ping'}],
  'options':{'num_predict':4}
}, timeout=90)
print('warm', r.status_code, r.elapsed.total_seconds())
PY""",
        timeout=120,
    )
    print(o2.read().decode(errors="replace")[:500])
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

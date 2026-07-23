#!/usr/bin/env python3
"""Report aus /tmp senden + Gunicorn Timeout + Env laden."""
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

SEND = r'''
import os, sqlite3
from pathlib import Path

# load .env
envp=Path("/root/app/backend/.env")
if envp.exists():
    for line in envp.read_text(errors="replace").splitlines():
        s=line.strip()
        if not s or s.startswith("#") or "=" not in s: continue
        k,v=s.split("=",1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

import telegram_ops
print("owners", telegram_ops.owner_chat_ids())
print("token", bool(telegram_ops.bot_token()))
text=Path("/tmp/nils_psa_report.txt").read_text(encoding="utf-8")
# fallback: last chat from log if owner missing
if not telegram_ops.owner_chat_ids():
    db=sqlite3.connect("/root/app/backend/orders.db")
    # try sessions empty; use env TELEGRAM from secrets file
    print("no owner in env")
    db.close()
out=telegram_ops.notify_owner(text)
print("TG", out)
if not out.get("ok"):
    # try direct send to known chat from recent webhook? check secrets local copy on server
    for p in [Path("/root/app/deploy.secrets.local"), Path("/root/deploy.secrets.local")]:
        if p.exists():
            for line in p.read_text(errors="replace").splitlines():
                if line.startswith("TELEGRAM_OWNER_CHAT_ID="):
                    cid=line.split("=",1)[1].strip().strip('"')
                    os.environ["TELEGRAM_OWNER_CHAT_ID"]=cid
                    print("loaded owner from", p, "…"+cid[-4:])
    out=telegram_ops.notify_owner(text)
    print("TG2", out)
'''


def main() -> int:
    c = paramiko.SSHClient()
    ssh_connect(c, timeout=25, banner_timeout=25, role="web")
    sftp = c.open_sftp()
    with sftp.file("/etc/systemd/system/snack-api.service", "w") as f:
        f.write(UNIT)
    with sftp.file("/tmp/nils_send_psa.py", "w") as f:
        f.write(SEND)
    # check report exists
    try:
        with sftp.file("/tmp/nils_psa_report.txt", "r") as f:
            preview = f.read(400)
            if isinstance(preview, bytes):
                preview = preview.decode("utf-8", errors="replace")
            print("REPORT_PREVIEW:\n", preview[:400])
    except Exception as e:
        print("no report", e)
    sftp.close()
    _, o, e = c.exec_command(
        "systemctl daemon-reload && systemctl restart snack-api && sleep 2 && "
        "systemctl is-active snack-api && "
        "cd /root/app/backend && /root/app/venv/bin/python /tmp/nils_send_psa.py",
        timeout=90,
    )
    print(o.read().decode(errors="replace")[:4000])
    err = e.read().decode(errors="replace")
    if err.strip():
        print("ERR", err[:1000])
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

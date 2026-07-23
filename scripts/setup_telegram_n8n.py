#!/usr/bin/env python3
"""Import Telegram Ops n8n workflow on auto-01."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import paramiko
from agency_config import ssh_connect

REMOTE = "/tmp/n8n-telegram-ops"
NAME = "Agency – Telegram Ops Bridge"
LOCAL = ROOT / "infra" / "n8n" / "workflow-telegram-ops.json"


def run(client, cmd: str, timeout: int = 120) -> str:
    _, o, e = client.exec_command(cmd, timeout=timeout)
    return (o.read() + e.read()).decode("utf-8", errors="replace").strip()


def main() -> int:
    auto = paramiko.SSHClient()
    ssh_connect(auto, timeout=25, banner_timeout=25, role="auto")
    run(auto, f"mkdir -p {REMOTE}")
    sftp = auto.open_sftp()
    sftp.put(str(LOCAL), f"{REMOTE}/{LOCAL.name}")
    sftp.close()
    print("upload ok")
    print(
        run(
            auto,
            f"export $(grep -v '^#' /opt/n8n/.env | xargs) && "
            f"N8N_USER_FOLDER=/opt/n8n/data n8n import:workflow --separate --input={REMOTE} 2>&1",
            timeout=180,
        )[:800]
    )
    act = f"""
import sqlite3
db='/opt/n8n/data/.n8n/database.sqlite'
conn=sqlite3.connect(db)
want={NAME!r}
for wid, name, active in conn.execute('SELECT id, name, active FROM workflow_entity'):
    if name == want:
        conn.execute('UPDATE workflow_entity SET active=1 WHERE id=?', (wid,))
        print('ON', name, wid)
conn.commit()
for wid, name, active in conn.execute("SELECT id, name, active FROM workflow_entity WHERE name LIKE '%Telegram%'"):
    print('STATE', int(active or 0), name)
conn.close()
"""
    sftp = auto.open_sftp()
    with sftp.file("/tmp/n8n_act_tg.py", "w") as f:
        f.write(act)
    sftp.close()
    print(run(auto, "python3 /tmp/n8n_act_tg.py"))
    run(auto, "systemctl restart n8n")
    time_sleep = run(auto, "sleep 3; systemctl is-active n8n")
    print("n8n", time_sleep)
    auto.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

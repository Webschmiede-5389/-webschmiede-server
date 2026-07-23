#!/usr/bin/env python3
"""Import Webschmiede n8n workflows via web-01 jump (wenn auto-01 direkt nicht erreichbar)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paramiko
from agency_config import ssh_connect, target_secrets

REMOTE = "/tmp/n8n-webschmiede-platform"
FILES = [
    "support-ticket.json",
    "contract-request.json",
    "contract-completed.json",
    "global-error-handler.json",
]


def run(client, cmd: str, timeout: int = 180) -> str:
    _, o, e = client.exec_command(cmd, timeout=timeout)
    return (o.read() + e.read()).decode("utf-8", errors="replace").strip()


def safe_print(msg: str) -> None:
    sys.stdout.buffer.write((msg + "\n").encode("utf-8", errors="replace"))
    sys.stdout.flush()


def main() -> int:
    auto = target_secrets("auto")
    auto_host = auto["SERVER_HOST"]

    web = paramiko.SSHClient()
    ssh_connect(web, timeout=45, banner_timeout=45, role="web")

    run(web, f"mkdir -p {REMOTE}")
    sftp = web.open_sftp()
    for name in FILES:
        local = ROOT / "infra" / "n8n" / name
        sftp.put(str(local), f"{REMOTE}/{name}")
        safe_print(f"web upload: {name}")
    sftp.close()

    for name in FILES:
        run(
            web,
            f"scp -o StrictHostKeyChecking=no {REMOTE}/{name} root@{auto_host}:{REMOTE}/",
            timeout=60,
        )

    import_out = run(
        web,
        f"ssh -o StrictHostKeyChecking=no root@{auto_host} "
        f"'export $(grep -v ^# /opt/n8n/.env | xargs); "
        f"N8N_USER_FOLDER=/opt/n8n/data n8n import:workflow --separate --input={REMOTE}'",
        timeout=240,
    )
    safe_print(import_out[:2000])

    activate_py = """
import sqlite3
conn=sqlite3.connect('/opt/n8n/data/.n8n/database.sqlite')
for wid, name, active in conn.execute('SELECT id, name, active FROM workflow_entity'):
    if name.startswith('Webschmiede') and 'Global Error Handler' not in name:
        conn.execute('UPDATE workflow_entity SET active=1 WHERE id=?', (wid,))
        print('ON', wid)
conn.commit()
conn.close()
"""
    sftp = web.open_sftp()
    with sftp.file("/tmp/n8n_act_ws.py", "w") as f:
        f.write(activate_py)
    sftp.close()
    run(web, f"scp -o StrictHostKeyChecking=no /tmp/n8n_act_ws.py root@{auto_host}:/tmp/n8n_act_ws.py")
    safe_print(run(web, f"ssh -o StrictHostKeyChecking=no root@{auto_host} python3 /tmp/n8n_act_ws.py"))

    safe_print(run(web, f"ssh -o StrictHostKeyChecking=no root@{auto_host} systemctl restart n8n"))
    web.close()
    safe_print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Import Webschmiede Platform n8n-Workflows (Support, Vertraege, Error Handler) auf auto-01."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paramiko
from agency_config import ssh_connect

REMOTE = "/tmp/n8n-webschmiede-platform"
N8N_DIR = ROOT / "infra" / "n8n"

WORKFLOWS = [
    "support-ticket.json",
    "contract-request.json",
    "contract-completed.json",
    "global-error-handler.json",
]

ACTIVATE_PREFIXES = [
    "Webschmiede",
]


def safe_print(msg: str) -> None:
    sys.stdout.buffer.write((msg + "\n").encode("utf-8", errors="replace"))
    sys.stdout.flush()


def run(client, cmd: str, timeout: int = 180) -> str:
    _, o, e = client.exec_command(cmd, timeout=timeout)
    return (o.read() + e.read()).decode("utf-8", errors="replace").strip()


def main() -> int:
    activate_only = "--activate-only" in sys.argv
    auto = paramiko.SSHClient()
    ssh_connect(auto, timeout=25, banner_timeout=25, role="auto")

    if not activate_only:
        run(auto, f"mkdir -p {REMOTE}")
        sftp = auto.open_sftp()
        for name in WORKFLOWS:
            local = N8N_DIR / name
            if not local.is_file():
                safe_print(f"FEHLT: {local}")
                return 1
            safe_print(f"upload {name}")
            sftp.put(str(local), f"{REMOTE}/{name}")
        sftp.close()
        safe_print(run(
            auto,
            f"export $(grep -v '^#' /opt/n8n/.env | xargs) && "
            f"N8N_USER_FOLDER=/opt/n8n/data n8n import:workflow --separate --input={REMOTE} 2>&1",
            timeout=240,
        )[:1200])

    activate_py = """
import sqlite3
db='/opt/n8n/data/.n8n/database.sqlite'
conn=sqlite3.connect(db)
prefixes = """ + repr(ACTIVATE_PREFIXES) + """
for wid, name, active in conn.execute('SELECT id, name, active FROM workflow_entity'):
    if any(name.startswith(p) for p in prefixes):
        if 'Global Error Handler' not in name:
            conn.execute('UPDATE workflow_entity SET active=1 WHERE id=?', (wid,))
            print('ON', wid)
conn.commit()
for wid, name, active in conn.execute("SELECT id, name, active FROM workflow_entity WHERE name LIKE 'Webschmiede%'"):
    print('STATE', int(active or 0), wid)
conn.close()
"""
    sftp = auto.open_sftp()
    with sftp.file("/tmp/n8n_act_ws_platform.py", "w") as f:
        f.write(activate_py)
    sftp.close()
    safe_print(run(auto, "python3 /tmp/n8n_act_ws_platform.py"))

    err_id = run(
        auto,
        "python3 -c \"import sqlite3;c=sqlite3.connect('/opt/n8n/data/.n8n/database.sqlite');"
        "r=c.execute(\\\"SELECT id FROM workflow_entity WHERE name LIKE '%Global Error Handler%' "
        "ORDER BY id DESC LIMIT 1\\\").fetchone();print(r[0] if r else '')\"",
    ).strip()
    if err_id.isdigit():
        safe_print(f"Error Workflow ID: {err_id}")
        safe_print(run(
            auto,
            f"python3 -c \"import sqlite3;c=sqlite3.connect('/opt/n8n/data/.n8n/database.sqlite');"
            f"c.execute('INSERT OR REPLACE INTO settings (key, value, loadOnStartup) VALUES (?, ?, 1)',"
            f"('workflow.defaultErrorWorkflow', '{err_id}', 1));c.commit();print('ok')\"",
        ))

    safe_print(run(auto, "systemctl restart n8n && sleep 4 && systemctl is-active n8n"))
    auto.close()
    safe_print("Fertig. Webhooks:")
    safe_print("  https://digitalehandwerkskunst.de/n8n/webhook/support-ticket")
    safe_print("  https://digitalehandwerkskunst.de/n8n/webhook/contract-request")
    safe_print("  https://digitalehandwerkskunst.de/n8n/webhook/contract-completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Importiert Agency-Hirn Workflows per SSH auf auto und aktiviert nur diese Namen."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paramiko
from agency_config import ssh_connect

REMOTE = "/tmp/n8n-agency-brain"
N8N_ENV = "/opt/n8n/.env"
NAMES = [
    "Agency – Hirn scharf (Router+Dispatch)",
    "Agency – AI Router (Dispatcher)",
    "Agency 01 – Router (Gehirn)",
    "Agency 02 – Stefan Guru-Filter + Plan",
]

FILES = [
    ROOT / "infra" / "n8n" / "workflow-agency-brain.json",
    ROOT / "infra" / "n8n" / "workflow-agency-router.json",
    ROOT / "infra" / "n8n" / "agency-system" / "01-router.json",
    ROOT / "infra" / "n8n" / "agency-system" / "02-stefan.json",
]


def run(client, cmd: str, timeout: int = 120) -> str:
    _, o, e = client.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    return (out + err).strip()


def main() -> int:
    sec = {}
    for line in (ROOT / "deploy.secrets.local").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            sec[k.strip()] = v.strip().strip('"')

    auto = paramiko.SSHClient()
    ssh_connect(auto, timeout=25, banner_timeout=25, role="auto")
    run(auto, f"mkdir -p {REMOTE}")
    sftp = auto.open_sftp()
    for path in FILES:
        if path.is_file():
            sftp.put(str(path), f"{REMOTE}/{path.name}")
            print("upload", path.name)
    # upsert env without printing secrets
    upsert = {
        "CRON_SECRET": sec.get("CRON_SECRET") or "",
        "AGENCY_ADMIN_PASSWORD": sec.get("AGENCY_ADMIN_PASSWORD") or "",
    }
    upsert = {k: v for k, v in upsert.items() if v}
    with sftp.file("/tmp/n8n_env_upsert.json", "w") as f:
        f.write(json.dumps(upsert))
    sftp.close()

    print(
        run(
            auto,
            "python3 - <<'PY'\n"
            "import json, pathlib\n"
            f"path=pathlib.Path('{N8N_ENV}')\n"
            "ups=json.loads(pathlib.Path('/tmp/n8n_env_upsert.json').read_text())\n"
            "lines=path.read_text().splitlines() if path.exists() else []\n"
            "keys=set()\n"
            "out=[]\n"
            "for line in lines:\n"
            "    if '=' in line and not line.strip().startswith('#'):\n"
            "        k=line.split('=',1)[0].strip()\n"
            "        if k in ups:\n"
            "            out.append(f'{k}={ups[k]}'); keys.add(k); continue\n"
            "    out.append(line)\n"
            "for k,v in ups.items():\n"
            "    if k not in keys: out.append(f'{k}={v}')\n"
            "path.write_text('\\n'.join(out)+('\\n' if out else ''))\n"
            "print('env keys', sorted(ups))\n"
            "PY",
        )
    )

    print(
        run(
            auto,
            f"export $(grep -v '^#' {N8N_ENV} | xargs) && "
            f"N8N_USER_FOLDER=/opt/n8n/data n8n import:workflow --separate --input={REMOTE} 2>&1",
            timeout=180,
        )[:1000]
    )

    names_json = json.dumps(NAMES)
    activate = (
        "import sqlite3, json\n"
        "db='/opt/n8n/data/.n8n/database.sqlite'\n"
        f"want=set(json.loads({names_json!r}))\n"
        "conn=sqlite3.connect(db)\n"
        "rows=conn.execute('SELECT id, name, active FROM workflow_entity').fetchall()\n"
        "for wid, name, active in rows:\n"
        "    if name in want:\n"
        "        conn.execute('UPDATE workflow_entity SET active=1 WHERE id=?', (wid,))\n"
        "        print('ON', name)\n"
        "conn.commit()\n"
        "for wid, name, active in conn.execute("
        "\"SELECT id, name, active FROM workflow_entity WHERE name LIKE 'Agency%'\"):\n"
        "    print('STATE', int(active or 0), name)\n"
        "conn.close()\n"
    )
    sftp = auto.open_sftp()
    with sftp.file("/tmp/n8n_activate_brain.py", "w") as f:
        f.write(activate)
    sftp.close()
    print(run(auto, "python3 /tmp/n8n_activate_brain.py; rm -f /tmp/n8n_env_upsert.json"))
    run(auto, "systemctl restart n8n")
    time.sleep(7)
    print("n8n", run(auto, "systemctl is-active n8n"))
    auto.close()
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Import + aktiviert Agency 14 Radar Wochen-Scan auf auto. Optional Freitag-Cron auf web."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paramiko
from agency_config import ssh_connect

REMOTE = "/tmp/n8n-agency-radar"
N8N_ENV = "/opt/n8n/.env"
NAME = "Agency 14 – Radar Wochen-Scan"
WF = ROOT / "infra" / "n8n" / "agency-system" / "14-radar.json"


def run(client, cmd: str, timeout: int = 120) -> str:
    _, o, e = client.exec_command(cmd, timeout=timeout)
    return (o.read() + e.read()).decode("utf-8", errors="replace").strip()


def main() -> int:
    # Freitag 07:00 Europe/Berlin (n8n cronExpression)
    raw = json.loads(WF.read_text(encoding="utf-8"))
    raw.pop("tags", None)
    for node in raw.get("nodes") or []:
        if node.get("name") == "Woechentlich":
            node["parameters"] = {
                "rule": {
                    "interval": [
                        {
                            "field": "cronExpression",
                            "expression": "0 7 * * 5",
                        }
                    ]
                }
            }
    raw["active"] = False
    WF.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sec = {}
    for line in (ROOT / "deploy.secrets.local").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            sec[k.strip()] = v.strip().strip('"')

    auto = paramiko.SSHClient()
    ssh_connect(auto, timeout=25, banner_timeout=25, role="auto")
    run(auto, f"mkdir -p {REMOTE}")
    sftp = auto.open_sftp()
    sftp.put(str(WF), f"{REMOTE}/14-radar.json")
    sftp.close()

    print(
        run(
            auto,
            f"export $(grep -v '^#' {N8N_ENV} | xargs) && "
            f"N8N_USER_FOLDER=/opt/n8n/data n8n import:workflow -i {REMOTE}/14-radar.json 2>&1",
            timeout=120,
        )[:600]
    )

    activate = f"""
import sqlite3
db='/opt/n8n/data/.n8n/database.sqlite'
conn=sqlite3.connect(db)
name={NAME!r}
row=conn.execute('SELECT id, active FROM workflow_entity WHERE name=?', (name,)).fetchone()
if not row:
    # fuzzy
    rows=conn.execute("SELECT id, name, active FROM workflow_entity WHERE name LIKE '%Radar%'").fetchall()
    print('found', rows)
    for wid, n, active in rows:
        conn.execute('UPDATE workflow_entity SET active=1 WHERE id=?', (wid,))
        print('ON', n)
else:
    conn.execute('UPDATE workflow_entity SET active=1 WHERE id=?', (row[0],))
    print('ON', name, row[0])
conn.commit()
for wid, n, a in conn.execute("SELECT id, name, active FROM workflow_entity WHERE name LIKE '%Radar%' OR name LIKE 'Agency 14%'"):
    print('STATE', int(a or 0), n)
conn.close()
"""
    sftp = auto.open_sftp()
    with sftp.file("/tmp/n8n_activate_radar.py", "w") as f:
        f.write(activate)
    sftp.close()
    print(run(auto, "python3 /tmp/n8n_activate_radar.py"))
    run(auto, "systemctl restart n8n")
    time.sleep(6)
    print("n8n", run(auto, "systemctl is-active n8n"))
    auto.close()

    # Backup: Freitag 07:05 auf web → API scan (schreibt Report auf web)
    web = paramiko.SSHClient()
    ssh_connect(web, timeout=25, banner_timeout=25, role="web")
    apw = sec.get("AGENCY_ADMIN_PASSWORD") or ""
    cron_line = (
        "5 7 * * 5 curl -sS -X POST http://127.0.0.1:8000/api/agency/radar/scan "
        '-H "Content-Type: application/json" '
        f'-H "X-Agency-Password: {apw}" '
        '-d \'{"live":true}\' >> /var/log/agency-radar.log 2>&1'
    )
    # write cron helper without echoing password in shell history oddly - use file
    sftp = web.open_sftp()
    with sftp.file("/root/app/scripts/radar_weekly.sh", "w") as f:
        f.write("#!/bin/bash\nset -euo pipefail\n")
        f.write('PW=$(grep "^AGENCY_ADMIN_PASSWORD=" /root/app/deploy.secrets.local | head -1 | cut -d= -f2- | tr -d "\\r")\n')
        f.write('curl -sS -X POST http://127.0.0.1:8000/api/agency/radar/scan \\\n')
        f.write('  -H "Content-Type: application/json" \\\n')
        f.write('  -H "X-Agency-Password: $PW" \\\n')
        f.write('  -d \'{"live":true}\' >> /var/log/agency-radar.log 2>&1\n')
        f.write('echo "radar ok $(date -Iseconds)" >> /var/log/agency-radar.log\n')
    sftp.close()
    print(
        run(
            web,
            "chmod +x /root/app/scripts/radar_weekly.sh; "
            "(crontab -l 2>/dev/null | grep -v radar_weekly | grep -v agency-radar; "
            "echo '5 7 * * 5 /root/app/scripts/radar_weekly.sh') | crontab -; "
            "crontab -l | grep radar || true",
        )
    )
    # Sofort einmal testen
    print("test", run(web, "/root/app/scripts/radar_weekly.sh; tail -n 3 /var/log/agency-radar.log", timeout=120)[-400:])
    web.close()
    print("OK: Radar Freitag 07:00 n8n + Freitag 07:05 web-Cron")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

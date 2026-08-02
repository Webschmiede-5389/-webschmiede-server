# -*- coding: utf-8 -*-
"""Upload + run staging entity-routing canary on web-01; fetch report."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import paramiko

SERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER))
from agency_config import ssh_connect  # noqa: E402

LOCAL_CANARY = SERVER / "scripts" / "canary_nils_entity_routing_staging.py"
REMOTE_CANARY = "/root/app/scripts/canary_nils_entity_routing_staging.py"
REMOTE_REPORT = "/root/app/data/nils-entity-routing-canary-report.json"
LOCAL_REPORT = (
    Path(r"C:\Users\kumex\OneDrive\Desktop\Jarvis\audits\infrastructure-audit-2026-07-29")
    / "nils-entity-routing-staging-canary-2026-08-02.json"
)


def main() -> int:
    client = paramiko.SSHClient()
    ssh_connect(client, role="web")
    sftp = client.open_sftp()
    try:
        sftp.put(str(LOCAL_CANARY), REMOTE_CANARY)
    finally:
        sftp.close()

    _, stdout, stderr = client.exec_command(
        f"/root/app/venv/bin/python {REMOTE_CANARY}",
        timeout=240,
    )
    out = (stdout.read() + stderr.read()).decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    print(out)

    sftp = client.open_sftp()
    try:
        try:
            sftp.get(REMOTE_REPORT, str(LOCAL_REPORT))
            print("SAVED_REPORT", LOCAL_REPORT)
            report = json.loads(LOCAL_REPORT.read_text(encoding="utf-8"))
            print("VERDICT", report.get("verdict"))
        except Exception as e:
            print("REPORT_FETCH_FAIL", e)
            report = {}
    finally:
        sftp.close()
        client.close()

    return code if code else (0 if report.get("verdict") == "READY_FOR_OWNER_CANARY" else 1)


if __name__ == "__main__":
    raise SystemExit(main())

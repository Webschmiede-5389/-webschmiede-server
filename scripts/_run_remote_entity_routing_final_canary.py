# -*- coding: utf-8 -*-
"""Run final A–H staging canary against NEW sqlite DB for current HEAD commit."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import paramiko

SERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER))
from agency_config import ssh_connect  # noqa: E402

LOCAL_CANARY = SERVER / "scripts" / "canary_nils_entity_routing_staging.py"
REMOTE_CANARY = "/root/app/scripts/canary_nils_entity_routing_staging.py"
REMOTE_REPORT = "/root/app/data/nils-entity-routing-final-canary-report.json"
LOCAL_REPORT = Path(
    r"C:\Users\kumex\OneDrive\Desktop\Jarvis\audits\infrastructure-audit-2026-07-29"
) / "nils-entity-routing-final-canary-2026-08-02.json"


def main() -> int:
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=str(SERVER), text=True
    ).strip()
    short = commit[:12]
    release_id = f"nils-entity-routing-{short}"
    staging_db = f"/root/app/data/nils-crm-staging-entity-{short}.db"

    client = paramiko.SSHClient()
    ssh_connect(client, role="web")
    sftp = client.open_sftp()
    try:
        sftp.put(str(LOCAL_CANARY), REMOTE_CANARY)
    finally:
        sftp.close()

    cmd = (
        f"export NILS_CRM_DB={staging_db}; "
        f"export NILS_RELEASE_ID={release_id}; "
        f"export NILS_GIT_COMMIT={commit}; "
        f"export NILS_RUNTIME_CODE_VERSION=2026-08-02-{short}; "
        f"/root/app/venv/bin/python {REMOTE_CANARY}"
    )
    _, stdout, stderr = client.exec_command(cmd, timeout=300)
    out = (stdout.read() + stderr.read()).decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    print(out)

    sftp = client.open_sftp()
    try:
        sftp.get(REMOTE_REPORT, str(LOCAL_REPORT))
        print("SAVED_REPORT", LOCAL_REPORT)
        report = json.loads(LOCAL_REPORT.read_text(encoding="utf-8"))
        print("VERDICT", report.get("verdict"))
        print("COMMIT", report.get("commit_id"))
        print("RELEASE", report.get("release_id"))
    except Exception as e:
        print("REPORT_FETCH_FAIL", e)
        report = {}
    finally:
        sftp.close()
        client.close()

    return code if code else (0 if "READY" in str(report.get("verdict") or "") else 1)


if __name__ == "__main__":
    raise SystemExit(main())

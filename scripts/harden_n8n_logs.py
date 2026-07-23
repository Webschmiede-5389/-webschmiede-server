#!/usr/bin/env python3
"""n8n Execution-Logs haerten (keine Success-Payloads dauerhaft speichern)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import paramiko
from agency_config import ssh_connect, target_secrets

ENV_FILE = "/opt/n8n/.env"
KEYS = {
    "EXECUTIONS_DATA_SAVE_ON_SUCCESS": "none",
    "EXECUTIONS_DATA_SAVE_ON_ERROR": "all",
    "EXECUTIONS_DATA_SAVE_MANUAL_EXECUTIONS": "false",
    "EXECUTIONS_DATA_PRUNE": "true",
    "EXECUTIONS_DATA_MAX_AGE": "168",
}


def main() -> int:
    _ = target_secrets("auto")
    client = paramiko.SSHClient()
    ssh_connect(client, timeout=20, banner_timeout=20, role="auto")

    def run(cmd: str, timeout: int = 90) -> str:
        _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        if err.strip():
            print("ERR:", err.strip()[:400])
        return out

    check = run(f"test -f {ENV_FILE} && echo OK || echo MISSING").strip()
    if "OK" not in check:
        print("n8n .env fehlt – Abbruch")
        return 1

    # Upsert keys without dumping secrets to local stdout
    for key, val in KEYS.items():
        run(
            f"grep -q '^{key}=' {ENV_FILE} "
            f"&& sed -i 's|^{key}=.*|{key}={val}|' {ENV_FILE} "
            f"|| echo '{key}={val}' >> {ENV_FILE}"
        )
    print("Updated keys:", ", ".join(KEYS))
    print(run("systemctl restart n8n && sleep 3 && systemctl is-active n8n").strip())
    # show only our keys (no passwords)
    print(run(f"grep -E '^({'|'.join(KEYS.keys())})=' {ENV_FILE}").strip())
    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

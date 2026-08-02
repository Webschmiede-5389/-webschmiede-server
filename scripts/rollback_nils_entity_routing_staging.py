# -*- coding: utf-8 -*-
"""Rollback Entity-Routing staging canary on web-01.

Restores backed-up nils_job_runtime modules + .env from
/root/app/backups/nils-entity-routing-2026-08-02-entity-routing-staging-1/
Dry-run: pass --dry-run
"""
from __future__ import annotations

import sys
from pathlib import Path

import paramiko

SERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER))
from agency_config import ssh_connect  # noqa: E402

CODE_VERSION = "2026-08-02-entity-routing-staging-1"
BACKUP_ROOT = f"/root/app/backups/nils-entity-routing-{CODE_VERSION}"
REMOTE_BACKEND = "/root/app/backend"


def run(client, cmd: str, timeout: int = 120) -> str:
    print("+", cmd[:220])
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = (stdout.read() + stderr.read()).decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[:4000].encode("ascii", "replace").decode("ascii"))
    if code != 0:
        raise RuntimeError(f"exit {code}")
    return out


def main() -> int:
    dry = "--dry-run" in sys.argv
    client = paramiko.SSHClient()
    ssh_connect(client, role="web")
    try:
        run(client, f"test -d {BACKUP_ROOT}/env && test -f {BACKUP_ROOT}/env/.env.bak")
        run(client, f"ls -la {BACKUP_ROOT}/nils_job_runtime | head -40")
        if dry:
            print("DRY_RUN_OK — would restore .env + modules from", BACKUP_ROOT)
            run(
                client,
                f"echo DRY; diff -q {BACKUP_ROOT}/env/.env.bak {REMOTE_BACKEND}/.env || true; "
                f"ls {BACKUP_ROOT}/nils_job_runtime | wc -l",
            )
            print("ROLLBACK_DRY_RUN_OK")
            return 0

        run(
            client,
            f"cp -a {BACKUP_ROOT}/env/.env.bak {REMOTE_BACKEND}/.env",
        )
        run(
            client,
            f"cp -a {BACKUP_ROOT}/nils_job_runtime/. {REMOTE_BACKEND}/nils_job_runtime/",
        )
        run(
            client,
            "rm -f /etc/systemd/system/nils-job-worker.service.d/entity-routing-staging.conf; "
            "systemctl daemon-reload; "
            "systemctl restart snack-api nils-job-worker; "
            "sleep 2; systemctl is-active snack-api nils-job-worker",
        )
        run(
            client,
            r"""cd /root/app/backend && /root/app/venv/bin/python - <<'PY'
from pathlib import Path
text=Path('.env').read_text()
assert 'NILS_CRM_BACKEND=sqlite' not in text or 'NILS_CRM_DATABASE_URL=' in text
# After rollback we expect previous production-oriented config restored from bak
print('ENV_RESTORED_OK')
for line in text.splitlines():
    if line.startswith('NILS_CRM_BACKEND=') or line.startswith('NILS_CONTROL_PLANE_CANARY=') or line.startswith('NILS_RUNTIME_CODE_VERSION='):
        print(line)
PY""",
        )
        print("ROLLBACK_OK", BACKUP_ROOT)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

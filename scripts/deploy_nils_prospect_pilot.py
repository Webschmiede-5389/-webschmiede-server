# -*- coding: utf-8 -*-
"""Deploy pilot-hardened nils_job_runtime release + optional env enable."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1]


def main() -> int:
    enable = "--enable" in sys.argv
    # 1) immutable release from current HEAD (includes pilot module)
    rc = subprocess.call(
        [sys.executable, str(SERVER / "scripts" / "deploy_nils_entity_routing_release.py")],
        cwd=str(SERVER),
    )
    if rc != 0:
        return rc

    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=str(SERVER), text=True
    ).strip()
    short = commit[:12]
    release_id = f"nils-entity-routing-{short}"

    # upload patch script
    import paramiko

    sys.path.insert(0, str(SERVER))
    from agency_config import ssh_connect  # noqa: E402

    client = paramiko.SSHClient()
    ssh_connect(client, role="web")
    sftp = client.open_sftp()
    try:
        sftp.put(
            str(SERVER / "scripts" / "_patch_env_prospect_pilot.py"),
            "/root/app/scripts/_patch_env_prospect_pilot.py",
        )
        sftp.put(
            str(SERVER / "scripts" / "pilot_nils_prospect_readonly.py"),
            "/root/app/scripts/pilot_nils_prospect_readonly.py",
        )
    finally:
        sftp.close()

    if enable:
        cmd = (
            f"/root/app/venv/bin/python /root/app/scripts/_patch_env_prospect_pilot.py "
            f"{release_id} {commit} 1 && "
            f"systemctl restart snack-api nils-job-worker && sleep 2 && "
            f"systemctl is-active snack-api nils-job-worker && "
            f"grep -E '^(NILS_CAP_CRM_PROSPECT_CREATE|NILS_CRM_BACKEND|NILS_CONTROL_PLANE_CANARY|NILS_CRM_TENANT_ID)=' /root/app/backend/.env"
        )
    else:
        cmd = (
            f"/root/app/venv/bin/python /root/app/scripts/_patch_env_prospect_pilot.py "
            f"{release_id} {commit} 0 && "
            f"systemctl restart snack-api nils-job-worker && sleep 2 && "
            f"systemctl is-active snack-api nils-job-worker"
        )
    _, stdout, stderr = client.exec_command(cmd, timeout=120)
    print((stdout.read() + stderr.read()).decode("utf-8", "replace"))
    code = stdout.channel.recv_exit_status()
    client.close()
    print("PILOT_DEPLOY", "ENABLE" if enable else "CODE_ONLY", release_id, commit)
    return code


if __name__ == "__main__":
    raise SystemExit(main())

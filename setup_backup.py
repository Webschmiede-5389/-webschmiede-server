#!/usr/bin/env python3
"""Tägliches Agency-Backup deployen + Cron."""
import os
import sys

import paramiko

sys.path.insert(0, os.path.dirname(__file__))
from agency_config import ssh_connect
from deploy_shell import upload_shell_script, verify_remote_shell

REMOTE = "/root/app/scripts/backup_agency.sh"
CRON = "0 3 * * * /bin/bash /root/app/scripts/backup_agency.sh >> /var/log/snack-backup.log 2>&1"


def run(client, cmd, timeout=60):
    _, out, err = client.exec_command(cmd, timeout=timeout)
    o = out.read().decode("utf-8", errors="replace").strip()
    e = err.read().decode("utf-8", errors="replace").strip()
    if o:
        print(o)
    if e and "WARNING" not in e.upper():
        print("ERR:", e[:400])
    return o


def main():
    local = os.path.join(os.path.dirname(__file__), "scripts", "backup_agency.sh")
    client = paramiko.SSHClient()
    ssh_connect(client)
    run(client, "mkdir -p /root/app/scripts /root/app/backups/daily")
    sftp = client.open_sftp()
    upload_shell_script(sftp, local, REMOTE)
    offsite = os.path.join(os.path.dirname(__file__), "scripts", "backup_offsite.sh")
    if os.path.isfile(offsite):
        upload_shell_script(sftp, offsite, "/root/app/scripts/backup_offsite.sh")
    sftp.close()
    run(client, f"chmod +x {REMOTE}")
    ok, msg = verify_remote_shell(client, REMOTE)
    if not ok:
        raise RuntimeError(msg)
    if os.path.isfile(offsite):
        run(client, "chmod +x /root/app/scripts/backup_offsite.sh")
        ok2, msg2 = verify_remote_shell(client, "/root/app/scripts/backup_offsite.sh")
        if not ok2:
            raise RuntimeError(msg2)
    run(
        client,
        "("
        "crontab -l 2>/dev/null | grep -v backup_agency.sh | grep -v backup_db.sh || true; "
        f"echo '{CRON}'"
        ") | crontab -",
    )
    run(client, "crontab -l | grep backup_agency || true")
    run(client, f"/bin/bash {REMOTE}", timeout=120)
    run(client, "tail -3 /var/log/snack-backup.log")
    client.close()
    print("\n=== FERTIG ===")
    print("Backup täglich 03:00 UTC, Aufbewahrung 7 Tage")
    print("Pfad: /root/app/backups/daily/")


if __name__ == "__main__":
    main()

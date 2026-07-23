#!/usr/bin/env python3
"""Nacht-Watchdog: Script deployen + Cron 04:15 + 10:15."""
import os
import sys

import paramiko

sys.path.insert(0, os.path.dirname(__file__))
from agency_config import load_secrets, ssh_connect
from deploy_shell import upload_shell_script, verify_remote_shell

REMOTE_SH = "/root/app/scripts/nightly_watchdog.sh"
CRON_NIGHT = "15 4 * * * /bin/bash /root/app/scripts/nightly_watchdog.sh >> /var/log/nightly-watchdog.log 2>&1"
CRON_MORNING = "15 10 * * * /bin/bash /root/app/scripts/nightly_watchdog.sh >> /var/log/nightly-watchdog.log 2>&1"


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
    local = os.path.join(os.path.dirname(__file__), "scripts", "nightly_watchdog.sh")
    client = paramiko.SSHClient()
    ssh_connect(client)
    run(client, "mkdir -p /root/app/scripts")
    sftp = client.open_sftp()
    upload_shell_script(sftp, local, REMOTE_SH)
    sftp.close()
    run(client, f"chmod +x {REMOTE_SH}")
    ok, msg = verify_remote_shell(client, REMOTE_SH)
    if not ok:
        raise RuntimeError(f"nightly_watchdog.sh Syntax-Fehler: {msg}")
    print("script_syntax_ok")

    run(
        client,
        "("
        "crontab -l 2>/dev/null | grep -v nightly_watchdog.sh || true; "
        f"echo '{CRON_NIGHT}'; "
        f"echo '{CRON_MORNING}'"
        ") | crontab -",
    )
    run(client, "crontab -l | grep nightly_watchdog || true")
    run(client, "systemctl restart snack-api", timeout=45)
    client.close()
    host = load_secrets()["SERVER_HOST"]
    print("\n=== FERTIG ===")
    print(f"Watchdog: POST http://{host}/api/cron/nightly-watchdog (CRON_SECRET)")
    print("Cron: 04:15 + 10:15 UTC -> /var/log/nightly-watchdog.log")
    print("Bei Fehler: E-Mail an AGENCY_OWNER_EMAIL")


if __name__ == "__main__":
    main()

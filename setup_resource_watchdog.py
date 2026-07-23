#!/usr/bin/env python3
"""Resource-Watchdog deployen + Cron alle 15 Min."""
import os
import sys

import paramiko

sys.path.insert(0, os.path.dirname(__file__))
from agency_config import load_secrets, ssh_connect
from deploy_shell import upload_shell_script, verify_remote_shell

REMOTE_SH = "/root/app/scripts/resource_watchdog.sh"
CRON_LINE = "*/15 * * * * /bin/bash /root/app/scripts/resource_watchdog.sh"


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
    local_sh = os.path.join(os.path.dirname(__file__), "scripts", "resource_watchdog.sh")
    client = paramiko.SSHClient()
    ssh_connect(client)
    run(client, "mkdir -p /root/app/scripts /var/lib/webschmiede")
    sftp = client.open_sftp()
    upload_shell_script(sftp, local_sh, REMOTE_SH)
    sftp.put(
        os.path.join(os.path.dirname(__file__), "app", "backend", "resource_watchdog.py"),
        "/root/app/backend/resource_watchdog.py",
    )
    sftp.close()
    run(client, f"chmod +x {REMOTE_SH}")
    ok, msg = verify_remote_shell(client, REMOTE_SH)
    if not ok:
        raise RuntimeError(f"resource_watchdog.sh Syntax-Fehler: {msg}")
    print("script_syntax_ok")
    run(
        client,
        "("
        "crontab -l 2>/dev/null | grep -v resource_watchdog.sh || true; "
        f"echo '{CRON_LINE}'"
        ") | crontab -",
    )
    run(client, "crontab -l | grep resource_watchdog || true")
    run(client, "cd /root/app/backend && python3 resource_watchdog.py --check-only --no-email | tail -c 500")
    client.close()
    print("\n=== FERTIG ===")
    print("Cron: alle 15 Min -> /var/log/resource-watchdog.log")
    print("Alerts: RAM-Warnung ab 85%, kritisch ab 92%, Disk ab 80%")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Install Ubuntu 24.04 on Hetzner server (must be in rescue mode).
Usage: NEW_AUTO_PASSWORD=... python scripts/install_ubuntu_rescue.py 88.198.170.156 auto-02
"""
from __future__ import annotations

import os
import sys
import time

import paramiko

INSTALL_CONF = """DRIVE1 /dev/sda
SWRAID 0
SWRAIDLEVEL 1
HOSTNAME {hostname}
PART /boot ext3 1024M
PART lvm vg0 all
LV vg0 root / ext4 100G
IMAGE /root/images/Ubuntu-2404-noble-amd64-base.tar.gz
"""


def run(client, cmd: str, timeout: int = 600) -> tuple[int, str]:
    _, out, err = client.exec_command(cmd, timeout=timeout)
    code = out.channel.recv_exit_status()
    text = (out.read() + err.read()).decode("utf-8", errors="replace")
    return code, text


def main() -> int:
    host = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("NEW_AUTO_HOST", "")
    hostname = sys.argv[2] if len(sys.argv) > 2 else "auto-02"
    password = os.environ.get("NEW_AUTO_PASSWORD", "")
    if not host or not password:
        print("Usage: NEW_AUTO_PASSWORD=... python scripts/install_ubuntu_rescue.py <ip> [hostname]")
        return 1

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(host, username="root", password=password, timeout=30, look_for_keys=False, allow_agent=False)

    _, o, _ = c.exec_command("hostname")
    hn = o.read().decode().strip()
    if hn != "rescue":
        print(f"SKIP: hostname={hn} (not rescue — Ubuntu vermutlich schon installiert)")
        c.close()
        return 0

    conf = INSTALL_CONF.format(hostname=hostname)
    sftp = c.open_sftp()
    with sftp.file("/tmp/webschmiede-install.conf", "w") as f:
        f.write(conf)
    sftp.close()

    print("Starte installimage (Server rebootet danach, ~5–10 Min.) …")
    code, text = run(c, "installimage -a -c /tmp/webschmiede-install.conf", timeout=900)
    print(text[-2000:] if len(text) > 2000 else text)
    c.close()
    if code != 0:
        print(f"installimage exit {code}")
        return 1

    print("Warte auf Reboot …")
    time.sleep(90)
    for i in range(24):
        time.sleep(15)
        try:
            c2 = paramiko.SSHClient()
            c2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c2.connect(host, username="root", password=password, timeout=15, look_for_keys=False, allow_agent=False)
            _, o2, _ = c2.exec_command("hostname; cat /etc/os-release | head -2")
            info = o2.read().decode().strip()
            c2.close()
            if "rescue" not in info.lower() and "ubuntu" in info.lower():
                print("OK Ubuntu erreichbar:", info.replace("\n", " | "))
                return 0
        except Exception:
            print(f"  … noch nicht da ({i + 1}/24)")
    print("WARN: Reboot-Check Timeout — manuell prüfen ob SSH geht")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

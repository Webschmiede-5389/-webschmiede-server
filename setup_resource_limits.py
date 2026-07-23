#!/usr/bin/env python3
"""n8n, snack-api und Cal.com auf kleinem Server begrenzen."""
import os
import sys

import paramiko

sys.path.insert(0, os.path.dirname(__file__))
from agency_config import ssh_connect

N8N_DROPIN = """[Service]
MemoryMax=1536M
CPUQuota=40%
"""

SNACK_DROPIN = """[Service]
MemoryMax=768M
CPUQuota=35%
"""

CALCOM_LIMITS = """
    mem_limit: 512m
    cpus: "0.5"
"""

DB_LIMITS = """
    mem_limit: 256m
    cpus: "0.25"
"""


def run(client, cmd, timeout=90):
    _, out, err = client.exec_command(cmd, timeout=timeout)
    o = out.read().decode("utf-8", errors="replace").strip()
    e = err.read().decode("utf-8", errors="replace").strip()
    if o:
        print(o)
    if e and "WARNING" not in e.upper():
        print("ERR:", e[:500])
    return o


def write_remote(sftp, path: str, content: str) -> None:
    with sftp.file(path, "w") as f:
        f.write(content)


def patch_gunicorn_workers(client) -> None:
    run(
        client,
        r"""
if grep -q 'systemd/snap' /etc/systemd/system/snack-api.service 2>/dev/null; then
  UNIT=/etc/systemd/system/snack-api.service
else
  UNIT=$(systemctl show -p FragmentPath snack-api | cut -d= -f2)
fi
echo "UNIT=$UNIT"
if [ -f "$UNIT" ]; then
  sed -i 's/-w [0-9]\+/-w 2/g; s/--workers [0-9]\+/--workers 2/g' "$UNIT" || true
  grep -E 'ExecStart|workers' "$UNIT" | head -3
fi
""",
    )


def main():
    client = paramiko.SSHClient()
    ssh_connect(client, timeout=25)
    sftp = client.open_sftp()

    run(client, "mkdir -p /etc/systemd/system/n8n.service.d /etc/systemd/system/snack-api.service.d")
    write_remote(sftp, "/etc/systemd/system/n8n.service.d/limits.conf", N8N_DROPIN)
    write_remote(sftp, "/etc/systemd/system/snack-api.service.d/limits.conf", SNACK_DROPIN)
    sftp.close()

    patch_gunicorn_workers(client)

    local_compose = os.path.join(os.path.dirname(__file__), "infra", "calcom", "docker-compose.yml")
    if os.path.isfile(local_compose):
        sftp = client.open_sftp()
        try:
            sftp.put(local_compose, "/opt/calcom/docker-compose.yml")
            print("calcom compose updated")
        except OSError as exc:
            print("calcom compose skip:", exc)
        sftp.close()

    run(client, "systemctl daemon-reload")
    run(client, "systemctl restart n8n snack-api")
    run(client, "sleep 3; systemctl is-active n8n snack-api")

    # Cal.com: stoppen (Setup-Phase), Limits in compose wenn wieder gestartet
    compose = "/opt/calcom/docker-compose.yml"
    run(
        client,
        f"test -f {compose} && docker compose -f {compose} stop 2>/dev/null || echo calcom_not_running",
        timeout=120,
    )

    run(client, "free -h; echo '---'; df -h / | tail -1; echo '---'; systemctl show n8n -p MemoryMax,CPUQuotaPerSecUSec --value")
    client.close()
    print("\n=== FERTIG ===")
    print("n8n: max 1.5 GB RAM, 40% CPU")
    print("snack-api: max 768 MB RAM, 2 Workers, 35% CPU")
    print("Cal.com: gestoppt (bei Bedarf: docker compose -f /opt/calcom/docker-compose.yml start)")


if __name__ == "__main__":
    main()

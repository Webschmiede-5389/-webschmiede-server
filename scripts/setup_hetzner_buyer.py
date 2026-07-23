# -*- coding: utf-8 -*-
"""Install Hetzner capacity buyer on auto-01 (cron every 5 min)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paramiko
from agency_config import target_secrets, SECRETS_FILE, _read_file_secrets

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "hetzner_capacity_buyer.py"
CRON_SH = ROOT / "scripts" / "hetzner_buyer_cron.sh"


def main():
    secrets = _read_file_secrets()
    token = secrets.get("HETZNER_API_TOKEN", "").strip()
    if not token:
        raise SystemExit("HETZNER_API_TOKEN fehlt lokal")

    t = target_secrets("auto")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(
        t["SERVER_HOST"],
        username=t["SERVER_USER"],
        password=t["SERVER_PASSWORD"],
        timeout=25,
        look_for_keys=False,
        allow_agent=False,
    )
    sftp = c.open_sftp()

    # ensure dirs
    for d in ("/root/app/scripts", "/var/lib/webschmiede", "/root/app"):
        try:
            sftp.stat(d)
        except OSError:
            # mkdir via shell
            pass

    def put(local: Path, remote: str, mode=0o755):
        sftp.put(str(local), remote)
        sftp.chmod(remote, mode)
        print("upload", remote)

    put(SCRIPT, "/root/app/scripts/hetzner_capacity_buyer.py", 0o755)
    # LF normalize cron shell
    text = CRON_SH.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    with sftp.file("/root/app/scripts/hetzner_buyer_cron.sh", "w") as f:
        f.write(text)
    sftp.chmod("/root/app/scripts/hetzner_buyer_cron.sh", 0o755)

    # merge token (+ mail) into auto deploy.secrets.local
    remote_path = "/root/app/deploy.secrets.local"
    existing = ""
    try:
        with sftp.file(remote_path, "r") as f:
            existing = f.read().decode("utf-8", "replace")
    except OSError:
        existing = ""
    vals = {}
    for line in existing.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        vals[k.strip()] = v.strip()
    for k in (
        "HETZNER_API_TOKEN",
        "AGENCY_OWNER_EMAIL",
        "AGENCY_MAIL_BCC",
        "AGENCY_SMTP_HOST",
        "AGENCY_SMTP_PORT",
        "AGENCY_SMTP_USER",
        "AGENCY_SMTP_PASS",
        "AGENCY_SMTP_FROM",
    ):
        if secrets.get(k):
            vals[k] = secrets[k]
    # ensure owner email for alerts
    if not vals.get("AGENCY_OWNER_EMAIL") and vals.get("AGENCY_MAIL_BCC"):
        vals["AGENCY_OWNER_EMAIL"] = vals["AGENCY_MAIL_BCC"]
    lines = [f"{k}={vals[k]}" for k in sorted(vals)]
    with sftp.file(remote_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    sftp.chmod(remote_path, 0o600)
    print("secrets updated on auto-01")
    sftp.close()

    # cron + dry-run
    cmd = r"""
set -e
mkdir -p /var/lib/webschmiede /var/log
chmod +x /root/app/scripts/hetzner_capacity_buyer.py /root/app/scripts/hetzner_buyer_cron.sh
# LF already ok
# install cron line
CRON_LINE='*/5 * * * * /bin/bash /root/app/scripts/hetzner_buyer_cron.sh'
(crontab -l 2>/dev/null | grep -v hetzner_buyer_cron || true; echo "$CRON_LINE") | crontab -
echo '--- crontab ---'
crontab -l | grep hetzner || true
echo '--- dry-run ---'
cd /root/app && python3 scripts/hetzner_capacity_buyer.py --dry-run
echo '--- status ---'
python3 /root/app/scripts/hetzner_capacity_buyer.py --status
"""
    _i, o, e = c.exec_command(cmd, timeout=90)
    print((o.read() + e.read()).decode("utf-8", "replace").encode("ascii", "replace").decode())
    c.close()
    print("OK: Buyer cron alle 5 Min auf auto-01")


if __name__ == "__main__":
    main()

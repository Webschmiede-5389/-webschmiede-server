#!/usr/bin/env python3
"""
Migrate auto-01 → new automation server (n8n, cron, /root/app scripts+akquise).
Requires: new server has Ubuntu (not rescue), NEW_AUTO_HOST + NEW_AUTO_PASSWORD in env
          or updated AUTO_* in deploy.secrets.local after OS install.

Updates web-01 nginx n8n proxy to new IP.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agency_config import ssh_connect, target_secrets, SECRETS_FILE, _read_file_secrets

N8N_UNIT = """[Unit]
Description=n8n workflow automation (Webschmiede)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/n8n
EnvironmentFile=/opt/n8n/.env
ExecStart=/usr/bin/n8n start
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""

BASE_PACKAGES = """
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv git curl ca-certificates ufw fail2ban rsync
"""

INSTALL_N8N = """
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y -qq nodejs
npm install -g n8n
"""

OLD_AUTO_HOST_DEFAULT = "204.168.174.152"


def connect_old_auto() -> paramiko.SSHClient:
    secrets = _read_file_secrets()
    host = os.environ.get("OLD_AUTO_HOST") or OLD_AUTO_HOST_DEFAULT
    new_host = os.environ.get("NEW_AUTO_HOST") or secrets.get("AUTO_HOST", "")
    if host == new_host:
        host = OLD_AUTO_HOST_DEFAULT
    pw = os.environ.get("OLD_AUTO_PASSWORD") or secrets.get("OLD_AUTO_PASSWORD") or secrets.get("SERVER_PASSWORD", "")
    if not pw:
        raise RuntimeError("OLD_AUTO_PASSWORD fehlt (alter auto-01)")
    return _connect(host, pw)


def _connect(host: str, password: str) -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(host, username="root", password=password, timeout=30, look_for_keys=False, allow_agent=False)
    return c


def run(c: paramiko.SSHClient, cmd: str, timeout: int = 300) -> tuple[int, str]:
    _, out, err = c.exec_command(cmd, timeout=timeout)
    code = out.channel.recv_exit_status()
    return code, (out.read() + err.read()).decode("utf-8", errors="replace")


def tar_paths_on_old(old: paramiko.SSHClient) -> str:
    """Create tarball on old auto-01."""
    paths = [
        "/opt/n8n",
        "/root/app/scripts",
        "/root/app/akquise",
        "/root/app/infra/n8n",
        "/root/app/deploy.secrets.local",
        "/root/app/backend/.env",
        "/root/app/kunden",
        "/root/app/n8n_kunde.py",
        "/root/app/kunden_ids.py",
        "/root/app/agency_config.py",
        "/var/lib/webschmiede",
    ]
    existing = []
    for p in paths:
        _, o, _ = old.exec_command(f"test -e {p} && echo ok")
        if o.read().decode().strip() == "ok":
            existing.append(p)
    tar_list = " ".join(existing)
    cmd = f"tar czf /tmp/auto-migrate.tgz {tar_list} 2>/dev/null; ls -la /tmp/auto-migrate.tgz"
    code, text = run(old, cmd, timeout=600)
    if code != 0 or "auto-migrate.tgz" not in text:
        raise RuntimeError(f"tar on old failed: {text[:300]}")
    return "/tmp/auto-migrate.tgz"


def transfer_tar(old: paramiko.SSHClient, new_ip: str, new_pw: str, remote_tar: str) -> None:
    """Stream tar old -> new via local temp (reliable on Windows)."""
    local = ROOT / "tmp_auto_migrate.tgz"
    sftp_o = old.open_sftp()
    print("Download tarball from auto-01 …")
    sftp_o.get(remote_tar, str(local))
    sftp_o.close()
    size_mb = local.stat().st_size / (1024 * 1024)
    print(f"  {size_mb:.1f} MB")

    new = _connect(new_ip, new_pw)
    sftp_n = new.open_sftp()
    print("Upload to new server …")
    sftp_n.put(str(local), "/tmp/auto-migrate.tgz")
    sftp_n.close()
    new.close()
    local.unlink(missing_ok=True)


def provision_new(new: paramiko.SSHClient) -> None:
    print("Basis-Pakete …")
    run(new, BASE_PACKAGES, timeout=600)
    code, out = run(new, "node -v 2>/dev/null || true")
    if "v" not in out:
        print("Node + n8n …")
        run(new, INSTALL_N8N, timeout=900)
    else:
        print(f"Node schon da ({out.strip()}), n8n …")
        run(new, "npm install -g n8n 2>/dev/null || true", timeout=600)
    run(new, "mkdir -p /opt/n8n /root/app /var/log /var/lib/webschmiede")


def extract_and_restore(new: paramiko.SSHClient, cron_text: str) -> None:
    run(new, "cd / && tar xzf /tmp/auto-migrate.tgz", timeout=600)
    run(new, "chmod +x /root/app/scripts/*.sh 2>/dev/null; true")

    if cron_text.strip():
        sftp = new.open_sftp()
        with sftp.file("/tmp/root.cron", "w") as f:
            f.write(cron_text.replace("\r\n", "\n"))
        sftp.close()
        run(new, "crontab /tmp/root.cron && rm -f /tmp/root.cron")

    # n8n systemd
    sftp = new.open_sftp()
    with sftp.file("/etc/systemd/system/n8n.service", "w") as f:
        f.write(N8N_UNIT)
    sftp.close()
    run(new, "systemctl daemon-reload && systemctl enable n8n && systemctl restart n8n")

    # ufw: ssh + n8n from web-01
    web = target_secrets("web")
    web_ip = web["SERVER_HOST"]
    run(new, f"""
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow from {web_ip} to any port 5678 proto tcp
ufw --force enable
""")


def patch_web_n8n_proxy(new_ip: str) -> None:
    site_paths = (
        "/etc/nginx/sites-available/digitalehandwerkskunst.de",
        "/etc/nginx/sites-enabled/digitalehandwerkskunst.de",
    )
    old_ips = {OLD_AUTO_HOST_DEFAULT, "204.168.174.152"}
    web = paramiko.SSHClient()
    ssh_connect(web, role="web")
    sftp = web.open_sftp()
    for site in site_paths:
        try:
            with sftp.open(site, "r") as f:
                cfg = f.read().decode("utf-8")
        except OSError:
            continue
        if new_ip in cfg and not any(o in cfg for o in old_ips if o != new_ip):
            continue
        for oip in old_ips:
            cfg = cfg.replace(f"http://{oip}:5678", f"http://{new_ip}:5678")
        with sftp.open(site, "w") as f:
            f.write(cfg)
        print(f"Patched n8n proxy in {site}")
    sftp.close()
    run(web, "nginx -t && systemctl reload nginx")
    web.close()


def update_local_secrets(new_ip: str, new_password: str) -> None:
    if not SECRETS_FILE.exists():
        return
    text = SECRETS_FILE.read_text(encoding="utf-8")
    lines = []
    seen_host = seen_pw = False
    for line in text.splitlines():
        if line.startswith("AUTO_HOST="):
            lines.append(f"AUTO_HOST={new_ip}")
            seen_host = True
        elif line.startswith("AUTO_PASSWORD="):
            lines.append(f"AUTO_PASSWORD={new_password}")
            seen_pw = True
        else:
            lines.append(line)
    if not seen_host:
        lines.append(f"AUTO_HOST={new_ip}")
    if not seen_pw and new_password:
        lines.append(f"AUTO_PASSWORD={new_password}")
    SECRETS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Updated {SECRETS_FILE.name} AUTO_HOST")


def smoke(new_ip: str, new_password: str) -> bool:
    c = _connect(new_ip, new_password)
    checks = []
    for cmd, needle in [
        ("systemctl is-active n8n", "active"),
        ("crontab -l | wc -l", ""),
        ("test -f /opt/n8n/.env && echo ok", "ok"),
    ]:
        _, o, _ = c.exec_command(cmd)
        out = o.read().decode().strip()
        checks.append((cmd, needle in out if needle else bool(out)))
    c.close()

    web = paramiko.SSHClient()
    ssh_connect(web, role="web")
    _, o, _ = web.exec_command(
        f'curl -sk -o /dev/null -w "%{{http_code}}" -H "Host: digitalehandwerkskunst.de" '
        f"https://127.0.0.1/n8n/"
    )
    n8n_code = o.read().decode().strip()
    web.close()
    print(f"n8n proxy HTTP: {n8n_code}")
    return n8n_code.startswith("2") or n8n_code == "401"


def main() -> int:
    secrets = _read_file_secrets()
    new_ip = os.environ.get("NEW_AUTO_HOST") or secrets.get("AUTO_HOST") or (sys.argv[1] if len(sys.argv) > 1 else "")
    new_pw = os.environ.get("NEW_AUTO_PASSWORD") or secrets.get("AUTO_PASSWORD", "")
    if not new_ip:
        print("Set NEW_AUTO_HOST or pass IP as argv[1]")
        return 1
    if not new_pw:
        print("NEW_AUTO_PASSWORD fehlt")
        return 1

    new = _connect(new_ip, new_pw)
    _, o, _ = new.exec_command("hostname")
    hn = o.read().decode().strip()
    if hn == "rescue":
        print("FEHLER: Server noch im Rescue-Modus. Zuerst Ubuntu installieren/rebuild.")
        new.close()
        return 1

    old = connect_old_auto()
    old_ip = os.environ.get("OLD_AUTO_HOST") or OLD_AUTO_HOST_DEFAULT

    print(f"Migriere auto-01 ({old_ip}) -> {new_ip} ({hn})")
    provision_new(new)
    new.close()

    remote_tar = tar_paths_on_old(old)
    _, o, _ = old.exec_command("crontab -l 2>/dev/null")
    cron_text = o.read().decode("utf-8", errors="replace")
    transfer_tar(old, new_ip, new_pw, remote_tar)
    run(old, "rm -f /tmp/auto-migrate.tgz")
    old.close()

    new = _connect(new_ip, new_pw)
    extract_and_restore(new, cron_text)
    new.close()

    patch_web_n8n_proxy(new_ip)
    update_local_secrets(new_ip, new_pw)

    ok = smoke(new_ip, new_pw)
    print("Migration OK" if ok else "Migration done — n8n proxy bitte manuell prüfen")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

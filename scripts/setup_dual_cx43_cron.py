#!/usr/bin/env python3
"""Installiert Dual-Watch Cron auf web + Cross-Backup-Hinweis auf web/auto."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paramiko
from agency_config import ssh_connect
from deploy_shell import upload_shell_script, verify_remote_shell


def _run(client, cmd: str, timeout: int = 60) -> str:
    _, o, e = client.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    if err.strip():
        print("ERR:", err.strip()[:300])
    return out


def main() -> int:
    cross = ROOT / "scripts" / "backup_cross_peers.sh"
    watch = ROOT / "scripts" / "dual_cx43_watch.py"

    # web: dual watch + cross backup role=web
    web = paramiko.SSHClient()
    ssh_connect(web, timeout=20, banner_timeout=20, role="web")
    _run(web, "mkdir -p /root/app/scripts /root/app/backend /root/app/backups/peer")
    sftp = web.open_sftp()
    upload_shell_script(sftp, str(cross), "/root/app/scripts/backup_cross_peers.sh")
    sftp.put(str(watch), "/root/app/scripts/dual_cx43_watch.py")
    sftp.put(str(ROOT / "app" / "backend" / "dual_infra.py"), "/root/app/backend/dual_infra.py")
    sftp.close()
    _run(web, "chmod +x /root/app/scripts/backup_cross_peers.sh /root/app/scripts/dual_cx43_watch.py")
    ok, msg = verify_remote_shell(web, "/root/app/scripts/backup_cross_peers.sh")
    print("web shell", ok, msg)
    # Cron: dual watch alle 30 Min; cross-backup taeglich 03:40
    cron = (
        "(crontab -l 2>/dev/null | grep -v dual_cx43_watch | grep -v backup_cross_peers; "
        "echo '*/30 * * * * cd /root/app && python3 scripts/dual_cx43_watch.py --mail-on-alert >> /var/log/dual-cx43.log 2>&1'; "
        "echo '40 3 * * * BACKUP_PEER_ROLE=web /root/app/scripts/backup_cross_peers.sh >> /var/log/snack-cross-backup.log 2>&1') "
        "| crontab -"
    )
    print(_run(web, cron))
    print("web crontab:", _run(web, "crontab -l | grep -E 'dual_cx43|cross' || true"))
    web.close()

    # auto: cross backup role=auto
    auto = paramiko.SSHClient()
    ssh_connect(auto, timeout=20, banner_timeout=20, role="auto")
    _run(auto, "mkdir -p /root/app/scripts /root/app/backups/peer")
    # secrets fuer Encrypt-Passphrase: von web kopieren falls fehlt
    _run(
        auto,
        "test -f /root/app/deploy.secrets.local || echo 'WARN: deploy.secrets.local auf auto fehlt fuer Encrypt'",
    )
    sftp = auto.open_sftp()
    upload_shell_script(sftp, str(cross), "/root/app/scripts/backup_cross_peers.sh")
    sftp.close()
    _run(auto, "chmod +x /root/app/scripts/backup_cross_peers.sh")
    cron_a = (
        "(crontab -l 2>/dev/null | grep -v backup_cross_peers; "
        "echo '50 3 * * * BACKUP_PEER_ROLE=auto /root/app/scripts/backup_cross_peers.sh >> /var/log/snack-cross-backup.log 2>&1') "
        "| crontab -"
    )
    print(_run(auto, cron_a))
    print("auto crontab:", _run(auto, "crontab -l | grep cross || true"))
    auto.close()
    print("Fertig. Peer-Push braucht BACKUP_PEER_* in secrets oder SSH-Key zwischen Hosts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

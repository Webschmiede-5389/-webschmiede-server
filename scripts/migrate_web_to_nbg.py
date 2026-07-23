#!/usr/bin/env python3
"""
Migrate web-01 (Helsinki CX33) → new web-01 in Germany (default: VOICE_HOST / Voice-01neu CX43).

Also moves Voice-Demo to AUTO_HOST if MOVE_VOICE=1 (default).

After run: update IONOS A-records to NEW_WEB_HOST (see docs/agency/ionos-dns.md).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agency_config import SECRETS_FILE, _read_file_secrets, ssh_connect, target_secrets

OLD_WEB_DEFAULT = "204.168.170.97"
LOCAL_TAR = ROOT / "tmp_web_migrate.tgz"

WEB_TAR_PATHS = [
    "/root/app",
    "/etc/nginx/sites-available",
    "/etc/nginx/sites-enabled",
    "/etc/letsencrypt",
    "/opt/calcom",
    "/etc/systemd/system/snack-api.service",
    "/var/www",
]

PROVISION_WEB = """
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq nginx certbot python3-certbot-nginx \
  python3 python3-pip python3-venv git curl ca-certificates ufw fail2ban rsync
hostnamectl set-hostname web-01neu
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
"""


def _stdout_safe() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _connect_host(host: str, password: str) -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(host, username="root", password=password, timeout=30, look_for_keys=False, allow_agent=False)
    return c


def run(c: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str]:
    print(f"$ {cmd[:100]}")
    _, out, err = c.exec_command(cmd, timeout=timeout)
    code = out.channel.recv_exit_status()
    text = (out.read() + err.read()).decode("utf-8", errors="replace")
    if text.strip():
        tail = text[-2500:] if len(text) > 2500 else text
        print(tail)
    return code, text


def connect_old_web() -> tuple[paramiko.SSHClient, str]:
    secrets = _read_file_secrets()
    host = os.environ.get("OLD_WEB_HOST") or secrets.get("WEB_HOST") or OLD_WEB_DEFAULT
    pw = os.environ.get("OLD_WEB_PASSWORD") or secrets.get("WEB_PASSWORD") or secrets.get("SERVER_PASSWORD", "")
    if not pw:
        raise RuntimeError("OLD_WEB_PASSWORD / WEB_PASSWORD fehlt")
    return _connect_host(host, pw), host


def resolve_new_web() -> tuple[str, str]:
    secrets = _read_file_secrets()
    host = os.environ.get("NEW_WEB_HOST") or secrets.get("NEW_WEB_HOST") or secrets.get("VOICE_HOST", "")
    pw = (
        os.environ.get("NEW_WEB_PASSWORD")
        or secrets.get("NEW_WEB_PASSWORD")
        or secrets.get("VOICE_PASSWORD")
        or secrets.get("WEB_PASSWORD")
        or ""
    )
    if not host or not pw:
        raise RuntimeError("NEW_WEB_HOST/VOICE_HOST und NEW_WEB_PASSWORD/VOICE_PASSWORD fehlen")
    return host, pw


def tar_on_old(old: paramiko.SSHClient) -> str:
    existing = []
    for p in WEB_TAR_PATHS:
        _, o, _ = old.exec_command(f"test -e {p} && echo ok")
        if o.read().decode().strip() == "ok":
            existing.append(p)
    if not existing:
        raise RuntimeError("Keine Pfade auf altem web-01 gefunden")
    cmd = f"tar czf /tmp/web-migrate.tgz {' '.join(existing)} 2>/tmp/web-tar.err; test -f /tmp/web-migrate.tgz && ls -la /tmp/web-migrate.tgz"
    code, text = run(old, cmd, timeout=900)
    if code != 0 or "web-migrate.tgz" not in text:
        raise RuntimeError(f"tar fehlgeschlagen: {text[:400]}")
    return "/tmp/web-migrate.tgz"


def transfer_tar(old: paramiko.SSHClient, remote_tar: str, new_ip: str, new_pw: str) -> None:
    print("Download von altem web-01 …")
    sftp = old.open_sftp()
    sftp.get(remote_tar, str(LOCAL_TAR))
    sftp.close()
    mb = LOCAL_TAR.stat().st_size / (1024 * 1024)
    print(f"  {mb:.1f} MB lokal")

    new = _connect_host(new_ip, new_pw)
    print("Upload auf neuen web-01 …")
    sftp_n = new.open_sftp()
    sftp_n.put(str(LOCAL_TAR), "/tmp/web-migrate.tgz")
    sftp_n.close()
    new.close()
    LOCAL_TAR.unlink(missing_ok=True)


def provision_new(new: paramiko.SSHClient) -> None:
    print("Basis-Pakete auf neuem Server …")
    run(new, PROVISION_WEB, timeout=900)
    run(new, "docker compose version 2>/dev/null || apt-get install -y -qq docker-compose-plugin", timeout=300)


def extract_and_start(new: paramiko.SSHClient, auto_ip: str) -> None:
    run(new, "cd / && tar xzf /tmp/web-migrate.tgz", timeout=600)
    run(new, "chmod +x /root/app/scripts/*.sh 2>/dev/null; true")
    run(new, "sed -i 's/\\r$//' /etc/systemd/system/snack-api.service 2>/dev/null; true")

    # Voice-Proxy → auto (Voice liegt nicht mehr auf diesem Host)
    run(
        new,
        f"grep -rl ':8090' /etc/nginx/sites-available /etc/nginx/sites-enabled 2>/dev/null | "
        f"xargs -r sed -i 's|http://[0-9.]\\+:8090|http://{auto_ip}:8090|g'",
        timeout=60,
    )

    run(new, "test -x /root/app/venv/bin/gunicorn || (cd /root/app && python3 -m venv venv && ./venv/bin/pip install -q -r backend/requirements.txt gunicorn)", timeout=900)
    run(new, "systemctl daemon-reload && systemctl enable snack-api nginx && systemctl restart snack-api nginx", timeout=120)

    run(
        new,
        "cd /opt/calcom && docker compose pull -q 2>/dev/null; docker compose up -d 2>/dev/null || true",
        timeout=600,
    )
    run(new, "nginx -t && systemctl reload nginx", timeout=60)
    run(new, "docker compose -f /root/app/infra/voice-demo/docker-compose.yml down 2>/dev/null || true")


def patch_auto_ufw(auto_ip: str, auto_pw: str, new_web_ip: str, old_web_ip: str) -> None:
    auto = _connect_host(auto_ip, auto_pw)
    run(
        auto,
        f"""
ufw allow from {new_web_ip} to any port 5678 proto tcp
ufw allow from {new_web_ip} to any port 8090 proto tcp
ufw status | grep -E '5678|8090|{new_web_ip}' || true
""",
        timeout=60,
    )
    auto.close()


def update_local_secrets(new_ip: str, new_pw: str) -> None:
    if not SECRETS_FILE.exists():
        return
    updates = {
        "WEB_HOST": new_ip,
        "WEB_PASSWORD": new_pw,
        "VOICE_HOST": "",  # Voice auf auto — Zeile leeren/entfernen unten
    }
    lines = []
    skip_voice = os.environ.get("KEEP_VOICE_HOST", "") != "1"
    for line in SECRETS_FILE.read_text(encoding="utf-8").splitlines():
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key in updates and updates[key]:
            lines.append(f"{key}={updates[key]}")
            updates.pop(key, None)
        elif skip_voice and key == "VOICE_HOST":
            lines.append(f"# VOICE_HOST=  # Voice auf AUTO_HOST :8090")
        elif skip_voice and key == "VOICE_PASSWORD":
            lines.append(f"# VOICE_PASSWORD=")
        else:
            lines.append(line)
    for k, v in updates.items():
        if v and k != "VOICE_HOST":
            lines.append(f"{k}={v}")
    SECRETS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Aktualisiert: {SECRETS_FILE.name} WEB_HOST={new_ip}")


def smoke(new_ip: str, new_pw: str) -> bool:
    c = _connect_host(new_ip, new_pw)
    ok = True
    for cmd, needle in [
        ("systemctl is-active snack-api", "active"),
        ("systemctl is-active nginx", "active"),
        ("curl -sf http://127.0.0.1:8000/api/health", "ok"),
    ]:
        _, o, _ = c.exec_command(cmd, timeout=30)
        out = o.read().decode("utf-8", errors="replace")
        good = needle.lower() in out.lower()
        print(f"  {'OK' if good else 'FAIL'}: {cmd} -> {out.strip()[:120]}")
        ok = ok and good
    c.close()
    return ok


def move_voice_to_auto() -> None:
    if os.environ.get("MOVE_VOICE", "1") != "1":
        print("MOVE_VOICE=0 — Voice-Migration übersprungen")
        return
    import subprocess

    print("\n=== Voice-Demo → auto-01neu ===")
    env = os.environ.copy()
    # remote_install nutzt VOICE_HOST — temporär AUTO
    secrets = _read_file_secrets()
    auto_ip = secrets.get("AUTO_HOST", "")
    auto_pw = secrets.get("AUTO_PASSWORD", "")
    if not auto_ip:
        print("AUTO_HOST fehlt — Voice manuell nachziehen")
        return
    # Patch remote_install to accept TARGET_ROLE — simpler: subprocess with env override
    script = ROOT / "scripts" / "remote_install_voice_demo.py"
    env["VOICE_HOST"] = auto_ip
    env["VOICE_PASSWORD"] = auto_pw
    r = subprocess.run([sys.executable, str(script)], cwd=str(ROOT), env=env)
    if r.returncode != 0:
        print("WARN: Voice-Install auf auto fehlgeschlagen — später manuell")
        return
    auto = paramiko.SSHClient()
    ssh_connect(auto, role="auto")
    run(auto, "bash /root/app/scripts/setup_voice_demo.sh > /var/log/voice-setup.log 2>&1; echo EXIT:$?", timeout=900)
    run(auto, "curl -sf http://127.0.0.1:8090/api/health || echo fail")
    auto.close()

    voice_ip = secrets.get("VOICE_HOST") or ""
    if voice_ip and voice_ip != auto_ip:
        try:
            vpw = secrets.get("VOICE_PASSWORD") or auto_pw
            v = _connect_host(voice_ip, vpw)
            run(v, "docker compose -f /root/app/infra/voice-demo/docker-compose.yml down 2>/dev/null || true")
            v.close()
        except Exception as ex:
            print(f"Voice alt stoppen: {ex}")


def main() -> int:
    _stdout_safe()
    new_ip, new_pw = resolve_new_web()
    secrets = _read_file_secrets()
    auto_ip = secrets.get("AUTO_HOST", "")

    new = _connect_host(new_ip, new_pw)
    _, o, _ = new.exec_command("hostname")
    if o.read().decode().strip() == "rescue":
        print("FEHLER: Ziel-Server im Rescue-Modus")
        new.close()
        return 1
    new.close()

    move_voice_to_auto()

    old, old_ip = connect_old_web()
    print(f"\n=== web-01 {old_ip} → {new_ip} (web-01neu) ===")

    if old_ip == new_ip:
        print("Quelle = Ziel — Abbruch")
        old.close()
        return 1

    remote_tar = tar_on_old(old)
    provision_new(_connect_host(new_ip, new_pw))
    transfer_tar(old, remote_tar, new_ip, new_pw)
    run(old, "rm -f /tmp/web-migrate.tgz")
    old.close()

    new = _connect_host(new_ip, new_pw)
    extract_and_start(new, auto_ip)
    new.close()

    auto_pw = secrets.get("AUTO_PASSWORD", "")
    if auto_ip and auto_pw:
        patch_auto_ufw(auto_ip, auto_pw, new_ip, old_ip)

    update_local_secrets(new_ip, new_pw)
    ok = smoke(new_ip, new_pw)

    print("\n" + "=" * 60)
    print(f"NEUE WEB-IP für IONOS DNS: {new_ip}")
    print("Alle A-Records von 204.168.170.97 auf diese IP stellen.")
    print("Danach Helsinki CX33 kündigen.")
    print("=" * 60)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

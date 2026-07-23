#!/usr/bin/env python3
"""
Security Phase 1 (Roadmap 1–4):
  1) Hetzner Cloud Firewall (SSH nur Admin-IP, HTTP/S öffentlich, Auto nur web→n8n/voice)
  2) HSTS in Nginx (web)
  3) Backup-Verschlüsselung (openssl AES) + Hinweis Offsite
  4) unattended-upgrades auf web + auto

Kein Storage-Box-Kauf. Offsite bleibt skip bis BACKUP_SFTP_* gesetzt.
"""
from __future__ import annotations

import json
import secrets as pysecrets
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agency_config import ssh_connect, _read_file_secrets

API = "https://api.hetzner.cloud/v1"
WEB_IP = "167.233.150.230"
AUTO_IP = "88.198.170.156"
FW_NAME = "webschmiede-dual"


def hetzner(method: str, path: str, token: str, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except Exception:
            parsed = {"raw": raw[:400]}
        return e.code, parsed


def normalize_lf(b: bytes) -> bytes:
    return b.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def run(c, cmd, t=180):
    print(f"$ {cmd[:120]}")
    _, o, e = c.exec_command(cmd, timeout=t)
    code = o.channel.recv_exit_status()
    text = (o.read() + e.read()).decode("utf-8", "replace")
    if text.strip():
        print(text[-2000:] if len(text) > 2000 else text)
    return code, text


def detect_admin_ip(c) -> str:
    _, o, _ = c.exec_command("echo $SSH_CLIENT", timeout=15)
    raw = o.read().decode("utf-8", "replace").strip()
    ip = raw.split()[0] if raw else ""
    if not ip or ip.startswith("127.") or ":" in ip and "." not in ip:
        # fallback: last successful ssh from auth.log
        _, o2, _ = c.exec_command(
            "grep 'Accepted' /var/log/auth.log 2>/dev/null | tail -5 | "
            "grep -oE '([0-9]{1,3}\\.){3}[0-9]{1,3}' | tail -1",
            timeout=15,
        )
        ip = o2.read().decode("utf-8", "replace").strip()
    return ip


def ensure_encrypt_passphrase(local: dict) -> str:
    """Ensure BACKUP_ENCRYPT_PASSPHRASE in local deploy.secrets.local (create if missing)."""
    path = ROOT / "deploy.secrets.local"
    existing = (local.get("BACKUP_ENCRYPT_PASSPHRASE") or "").strip()
    if existing:
        return existing
    # also check ionos-style side files — none
    phrase = pysecrets.token_urlsafe(32)
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    if "BACKUP_ENCRYPT_PASSPHRASE=" in text:
        # empty value — replace
        lines = []
        for line in text.splitlines():
            if line.startswith("BACKUP_ENCRYPT_PASSPHRASE="):
                lines.append(f"BACKUP_ENCRYPT_PASSPHRASE={phrase}")
            else:
                lines.append(line)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        with path.open("a", encoding="utf-8") as f:
            f.write("\n# Backup encryption (keep offline copy!)\n")
            f.write(f"BACKUP_ENCRYPT_PASSPHRASE={phrase}\n")
    print("BACKUP_ENCRYPT_PASSPHRASE neu erzeugt (nur lokal in deploy.secrets.local)")
    return phrase


def setup_hetzner_firewall(token: str, admin_ip: str) -> None:
    print(f"\n=== Hetzner Firewall (Admin-IP {admin_ip}) ===")
    if not admin_ip:
        raise SystemExit("Keine Admin-IP – Firewall abgebrochen (Lockout-Schutz)")

    code, data = hetzner("GET", "/firewalls", token)
    if code != 200:
        raise SystemExit(f"Firewalls list HTTP {code}: {data}")
    fw = next((f for f in data.get("firewalls") or [] if f.get("name") == FW_NAME), None)

    rules = [
        {
            "direction": "in",
            "protocol": "tcp",
            "port": "22",
            "source_ips": [f"{admin_ip}/32"],
            "description": "SSH admin only",
        },
        {
            "direction": "in",
            "protocol": "tcp",
            "port": "80",
            "source_ips": ["0.0.0.0/0", "::/0"],
            "description": "HTTP",
        },
        {
            "direction": "in",
            "protocol": "tcp",
            "port": "443",
            "source_ips": ["0.0.0.0/0", "::/0"],
            "description": "HTTPS",
        },
        {
            "direction": "in",
            "protocol": "tcp",
            "port": "5678",
            "source_ips": [f"{WEB_IP}/32"],
            "description": "n8n from web only",
        },
        {
            "direction": "in",
            "protocol": "tcp",
            "port": "8090",
            "source_ips": [f"{WEB_IP}/32"],
            "description": "voice from web only",
        },
        {
            "direction": "in",
            "protocol": "icmp",
            "source_ips": ["0.0.0.0/0", "::/0"],
            "description": "ICMP",
        },
    ]

    if fw:
        fid = fw["id"]
        print(f"Firewall existiert id={fid}, update rules…")
        c2, body = hetzner("POST", f"/firewalls/{fid}/actions/set_rules", token, {"rules": rules})
        print(f"  set_rules HTTP {c2}")
    else:
        print("Erstelle Firewall…")
        c2, body = hetzner(
            "POST",
            "/firewalls",
            token,
            {"name": FW_NAME, "rules": rules},
        )
        print(f"  create HTTP {c2}")
        if c2 not in (200, 201):
            raise SystemExit(f"Firewall create failed: {body}")
        fid = (body.get("firewall") or {}).get("id")
        if not fid:
            raise SystemExit(f"Keine firewall id: {body}")

    # apply to servers by IP
    code, sdata = hetzner("GET", "/servers", token)
    servers = sdata.get("servers") or []
    apply = []
    for s in servers:
        ip = ((s.get("public_net") or {}).get("ipv4") or {}).get("ip")
        if ip in (WEB_IP, AUTO_IP):
            apply.append({"type": "server", "server": {"id": s["id"]}})
            print(f"  apply -> {s.get('name')} ({ip})")
    if apply:
        c3, b3 = hetzner(
            "POST",
            f"/firewalls/{fid}/actions/apply_to_resources",
            token,
            {"apply_to": apply},
        )
        print(f"  apply_to_resources HTTP {c3} {str(b3)[:200]}")
        time.sleep(3)
    print("Firewall OK")


def patch_hsts_web():
    print("\n=== HSTS Nginx (web) ===")
    c = paramiko.SSHClient()
    ssh_connect(c, role="web")
    # snippet in conf.d — applies to all HTTPS servers that inherit; safer: inject into each ssl server
    snippet = (
        "# Webschmiede HSTS\n"
        "add_header Strict-Transport-Security \"max-age=31536000; includeSubDomains\" always;\n"
    )
    sftp = c.open_sftp()
    with sftp.file("/etc/nginx/conf.d/hsts.conf", "w") as f:
        f.write(snippet)
    sftp.close()
    # Note: add_header in conf.d http context may not work — nginx add_header in http{} is invalid.
    # Use include in each server or map. Better approach: sed into all sites-enabled ssl servers.
    run(c, "rm -f /etc/nginx/conf.d/hsts.conf")
    py = r'''
from pathlib import Path
HSTS = '    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;'
root = Path("/etc/nginx/sites-enabled")
changed = 0
for p in list(root.iterdir()) + list(Path("/etc/nginx/sites-available").iterdir()):
    if not p.is_file():
        continue
    text = p.read_text(encoding="utf-8", errors="replace")
    if "Strict-Transport-Security" in text:
        continue
    if "listen 443" not in text and "listen [::]:443" not in text:
        continue
    # insert after first ssl_certificate_key or listen 443 block start
    lines = text.splitlines()
    out = []
    inserted = False
    for i, line in enumerate(lines):
        out.append(line)
        if not inserted and ("ssl_certificate_key" in line or (line.strip().startswith("listen") and "443" in line and "ssl" in line)):
            # look ahead: insert once after ssl lines cluster
            pass
    # simpler: after first "ssl_certificate_key" line
    out = []
    inserted = False
    for line in lines:
        out.append(line)
        if not inserted and "ssl_certificate_key" in line:
            out.append(HSTS)
            inserted = True
    if not inserted:
        # after server_name in 443 server — fallback after first listen 443 ssl
        out = []
        for line in lines:
            out.append(line)
            if not inserted and "listen" in line and "443" in line:
                out.append(HSTS)
                inserted = True
    if inserted:
        p.write_text("\n".join(out) + "\n", encoding="utf-8")
        changed += 1
        print(f"HSTS -> {p}")
print(f"changed={changed}")
'''
    sftp = c.open_sftp()
    with sftp.file("/tmp/patch_hsts.py", "w") as f:
        f.write(py)
    sftp.close()
    run(c, "python3 /tmp/patch_hsts.py")
    code, _ = run(c, "nginx -t && systemctl reload nginx")
    if code != 0:
        print("WARN nginx HSTS")
    # verify header
    run(
        c,
        "curl -skI https://127.0.0.1/api/health -H 'Host: digitalehandwerkskunst.de' | "
        "grep -i strict-transport || echo 'HSTS header missing'",
    )
    c.close()


def setup_backup_encrypt(phrase: str, local: dict):
    print("\n=== Backup encrypt ===")
    path = ROOT / "scripts" / "backup_agency.sh"
    offsite = ROOT / "scripts" / "backup_offsite.sh"

    for role in ("web", "auto"):
        c = paramiko.SSHClient()
        ssh_connect(c, role=role)
        sftp = c.open_sftp()
        run(c, "mkdir -p /root/app/scripts /root/app/backups/daily /var/lib/webschmiede")
        for src, rem in (
            (path, "/root/app/scripts/backup_agency.sh"),
            (offsite, "/root/app/scripts/backup_offsite.sh"),
        ):
            if not src.is_file():
                continue
            with sftp.file(rem, "wb") as f:
                f.write(normalize_lf(src.read_bytes()))
            print(f"put {rem}")

        remote = "/root/app/deploy.secrets.local"
        existing: dict[str, str] = {}
        try:
            with sftp.file(remote, "r") as f:
                for line in f.read().decode("utf-8", "replace").splitlines():
                    s = line.strip()
                    if not s or s.startswith("#") or "=" not in s:
                        continue
                    k, v = s.split("=", 1)
                    existing[k.strip()] = v.strip()
        except OSError:
            pass
        for k in (
            "WEB_HOST",
            "AUTO_HOST",
            "AGENCY_OWNER_EMAIL",
            "AGENCY_SMTP_HOST",
            "AGENCY_SMTP_PORT",
            "AGENCY_SMTP_USER",
            "AGENCY_SMTP_PASS",
            "AGENCY_SMTP_FROM",
            "BACKUP_SFTP_HOST",
            "BACKUP_SFTP_USER",
            "BACKUP_SFTP_PASS",
            "BACKUP_SFTP_PATH",
        ):
            if local.get(k):
                existing[k] = local[k]
        existing["BACKUP_ENCRYPT_PASSPHRASE"] = phrase
        blob = ("\n".join(f"{k}={v}" for k, v in existing.items()) + "\n").encode("utf-8")
        with sftp.file(remote, "w") as f:
            f.write(blob)
        sftp.close()
        run(c, "chmod 600 /root/app/deploy.secrets.local; chmod +x /root/app/scripts/backup_agency.sh /root/app/scripts/backup_offsite.sh")
        run(c, "sed -i 's/\\r$//' /root/app/scripts/backup_agency.sh /root/app/scripts/backup_offsite.sh")
        run(
            c,
            "("
            "crontab -l 2>/dev/null | grep -v backup_agency.sh || true; "
            "echo '0 3 * * * /bin/bash /root/app/scripts/backup_agency.sh >> /var/log/snack-backup.log 2>&1'"
            ") | crontab -",
        )
        if role == "web":
            run(c, "/bin/bash /root/app/scripts/backup_agency.sh", t=120)
            run(c, "tail -10 /var/log/snack-backup.log")
            run(c, "ls -la /root/app/backups/daily | tail -5")
        c.close()
        print(f"{role}: backup script + passphrase synced")


def setup_unattended(role: str):
    print(f"\n=== unattended-upgrades ({role}) ===")
    c = paramiko.SSHClient()
    ssh_connect(c, role=role)
    run(
        c,
        "export DEBIAN_FRONTEND=noninteractive; "
        "apt-get update -qq && apt-get install -y -qq unattended-upgrades apt-listchanges >/dev/null && "
        "echo unattended_installed",
        t=300,
    )
    conf = """APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
"""
    sftp = c.open_sftp()
    with sftp.file("/etc/apt/apt.conf.d/20auto-upgrades", "w") as f:
        f.write(conf)
    sftp.close()
    run(c, "unattended-upgrade --dry-run --debug 2>&1 | tail -15 || true", t=120)
    c.close()


def chmod_secrets():
    print("\n=== Dateirechte .env / db ===")
    for role in ("web", "auto"):
        c = paramiko.SSHClient()
        ssh_connect(c, role=role)
        run(
            c,
            "chmod 600 /root/app/deploy.secrets.local 2>/dev/null || true; "
            "chmod 600 /root/app/backend/.env 2>/dev/null || true; "
            "chmod 600 /root/app/backend/orders.db 2>/dev/null || true; "
            "ls -la /root/app/deploy.secrets.local /root/app/backend/.env /root/app/backend/orders.db 2>/dev/null | head -5",
        )
        c.close()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    local = _read_file_secrets()
    # merge ionos file keys if present
    ion = ROOT / "ionos-api.local.txt"
    if ion.is_file():
        for line in ion.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            local[k.strip()] = v.strip()

    token = (local.get("HETZNER_API_TOKEN") or "").strip()
    if not token:
        print("HETZNER_API_TOKEN fehlt")
        return 1

    # Admin IP from web SSH session
    web = paramiko.SSHClient()
    ssh_connect(web, role="web")
    admin_ip = detect_admin_ip(web)
    print(f"Admin-IP (diese Session): {admin_ip}")
    web.close()

    # Allow override
    if (ROOT / "admin-ip.local.txt").is_file():
        override = (ROOT / "admin-ip.local.txt").read_text(encoding="utf-8").strip().splitlines()[0].strip()
        if override and not override.startswith("#"):
            admin_ip = override
            print(f"Admin-IP Override: {admin_ip}")

    setup_hetzner_firewall(token, admin_ip)
    patch_hsts_web()
    phrase = ensure_encrypt_passphrase(local)
    local["BACKUP_ENCRYPT_PASSPHRASE"] = phrase
    setup_backup_encrypt(phrase, local)
    setup_unattended("web")
    setup_unattended("auto")
    chmod_secrets()

    # verify SSH still works after firewall
    print("\n=== SSH-Check nach Firewall ===")
    time.sleep(2)
    for role in ("web", "auto"):
        try:
            c = paramiko.SSHClient()
            ssh_connect(c, role=role)
            run(c, "echo ssh_ok_$(hostname)")
            c.close()
        except Exception as e:
            print(f"FAIL SSH {role}: {e}")
            return 1

    print("\nFERTIG Phase 1")
    print("Offsite: noch skip bis Storage Box + BACKUP_SFTP_* (kein Kauf ohne OK)")
    print("Backup-Passphrase liegt in deploy.secrets.local — zusätzlich offline sichern!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

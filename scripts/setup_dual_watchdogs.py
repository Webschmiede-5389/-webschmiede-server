#!/usr/bin/env python3
"""Install Watchdogs + Schränke auf web-01neu UND auto-01neu (15-Min-Takt)."""
from __future__ import annotations

import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agency_config import ssh_connect, _read_file_secrets


def normalize_lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def run(c, cmd, t=120):
    print(f"$ {cmd[:130]}")
    _, o, e = c.exec_command(cmd, timeout=t)
    code = o.channel.recv_exit_status()
    text = (o.read() + e.read()).decode("utf-8", "replace")
    if text.strip():
        print(text[-1600:] if len(text) > 1600 else text)
    return code, text


def put(sftp, local: Path, remote: str, shell: bool = False):
    if not local.is_file():
        print(f"SKIP missing {local}")
        return
    data = local.read_bytes()
    data = normalize_lf(data) if shell else data.replace(b"\r\n", b"\n")
    with sftp.file(remote, "wb") as f:
        f.write(data)
    print(f"put {remote}")


def merge_secrets(sftp, local: dict):
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
        "IONOS_API_PREFIX",
        "IONOS_API_SECRET",
    ):
        if local.get(k):
            existing[k] = local[k]
    data = ("\n".join(f"{k}={v}" for k, v in existing.items()) + "\n").encode("utf-8")
    with sftp.file(remote, "w") as f:
        f.write(data)


def upload_common(sftp, c):
    run(c, "mkdir -p /root/app/scripts /root/app/backend/integrations /root/app/kunden /var/lib/webschmiede/cabinets")
    files = [
        (ROOT / "app/backend/watchdog_cabinets.py", "/root/app/backend/watchdog_cabinets.py", False),
        (ROOT / "app/backend/resource_watchdog.py", "/root/app/backend/resource_watchdog.py", False),
        (ROOT / "app/backend/agency_mail.py", "/root/app/backend/agency_mail.py", False),
        (ROOT / "app/backend/integrations/ionos_dns.py", "/root/app/backend/integrations/ionos_dns.py", False),
        (ROOT / "scripts/route_watchdog.py", "/root/app/scripts/route_watchdog.py", False),
        (ROOT / "scripts/route_watchdog.sh", "/root/app/scripts/route_watchdog.sh", True),
        (ROOT / "scripts/resource_watchdog.sh", "/root/app/scripts/resource_watchdog.sh", True),
        (ROOT / "scripts/customer_portal_watchdog.py", "/root/app/scripts/customer_portal_watchdog.py", False),
        (ROOT / "scripts/customer_portal_watchdog.sh", "/root/app/scripts/customer_portal_watchdog.sh", True),
    ]
    for src, rem, shell in files:
        put(sftp, src, rem, shell=shell)
    # kunden json
    for path in (ROOT / "kunden").glob("*.json"):
        put(sftp, path, f"/root/app/kunden/{path.name}")
    run(c, "touch /root/app/backend/__init__.py /root/app/backend/integrations/__init__.py")
    run(
        c,
        "chmod +x /root/app/scripts/route_watchdog.sh "
        "/root/app/scripts/resource_watchdog.sh "
        "/root/app/scripts/customer_portal_watchdog.sh",
    )
    run(
        c,
        "sed -i 's/\\r$//' /root/app/scripts/route_watchdog.sh "
        "/root/app/scripts/resource_watchdog.sh "
        "/root/app/scripts/customer_portal_watchdog.sh",
    )


def install_web(local: dict):
    print("\n=== WEB ===")
    c = paramiko.SSHClient()
    ssh_connect(c, role="web")
    sftp = c.open_sftp()
    upload_common(sftp, c)
    merge_secrets(sftp, local)
    sftp.close()
    # Web: resource + customer portal + route (API/DNS from web perspective)
    # Offset minutes so both servers don't spike together
    run(
        c,
        "("
        "crontab -l 2>/dev/null | grep -vE 'resource_watchdog|customer_portal_watchdog|route_watchdog' || true; "
        "echo '*/15 * * * * /bin/bash /root/app/scripts/resource_watchdog.sh'; "
        "echo '5,20,35,50 * * * * /bin/bash /root/app/scripts/customer_portal_watchdog.sh'; "
        "echo '10,25,40,55 * * * * /bin/bash /root/app/scripts/route_watchdog.sh'"
        ") | crontab -",
    )
    run(c, "crontab -l")
    run(c, "cd /root/app/backend && python3 -c 'from watchdog_cabinets import flock; print(\"cabinets_ok\")'")
    run(c, "/usr/bin/python3 /root/app/scripts/customer_portal_watchdog.py --dry-run", t=90)
    c.close()


def install_auto(local: dict):
    print("\n=== AUTO ===")
    c = paramiko.SSHClient()
    ssh_connect(c, role="auto")
    sftp = c.open_sftp()
    upload_common(sftp, c)
    merge_secrets(sftp, local)
    sftp.close()
    # Keep existing crons; ensure route + resource + customer + stefan
    run(
        c,
        "("
        "crontab -l 2>/dev/null | grep -vE 'resource_watchdog|customer_portal_watchdog|route_watchdog' || true; "
        # re-add other lines that we just filtered? NO - we filtered only those three.
        # Wait - grep -v removes them from listing, then we need ALL other lines preserved.
        # The pipeline takes crontab -l | grep -v … so other jobs stay. Good.
        "echo '*/15 * * * * /bin/bash /root/app/scripts/resource_watchdog.sh'; "
        "echo '*/15 * * * * /bin/bash /root/app/scripts/route_watchdog.sh'; "
        "echo '8,23,38,53 * * * * /bin/bash /root/app/scripts/customer_portal_watchdog.sh'"
        ") | crontab -",
    )
    run(c, "crontab -l | grep -E 'watchdog|stefan|portal' || true")
    run(c, "/usr/bin/python3 /root/app/scripts/route_watchdog.py --dry-run", t=90)
    c.close()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    local = _read_file_secrets()
    # also load ionos file
    ion = ROOT / "ionos-api.local.txt"
    if ion.is_file():
        for line in ion.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            local[k.strip()] = v.strip()
    install_web(local)
    install_auto(local)
    print("\nFERTIG: Schränke + 15-Min-Takt auf beiden Servern")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

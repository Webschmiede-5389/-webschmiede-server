#!/usr/bin/env python3
"""Upload Stefan digest + secrets keys + agency_mail, install cron, optional --send."""
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
    print(f"$ {cmd[:100]}")
    _, o, e = c.exec_command(cmd, timeout=t)
    code = o.channel.recv_exit_status()
    text = (o.read() + e.read()).decode("utf-8", "replace")
    if text.strip():
        print(text[-1800:] if len(text) > 1800 else text)
    return code, text


def merge_secrets_on_remote(c, sftp, local_secrets: dict[str, str]) -> None:
    """Ensure WEB_HOST, AUTO_HOST, SMTP keys exist on auto (no print of values)."""
    remote = "/root/app/deploy.secrets.local"
    keys_needed = [
        "WEB_HOST",
        "AUTO_HOST",
        "AGENCY_OWNER_EMAIL",
        "AGENCY_SMTP_HOST",
        "AGENCY_SMTP_PORT",
        "AGENCY_SMTP_USER",
        "AGENCY_SMTP_PASS",
        "AGENCY_SMTP_FROM",
    ]
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

    for k in keys_needed:
        if local_secrets.get(k):
            existing[k] = local_secrets[k]

    # Keep other keys
    lines = [f"{k}={v}" for k, v in existing.items()]
    data = ("\n".join(lines) + "\n").encode("utf-8")
    with sftp.file(remote, "w") as f:
        f.write(data)
    print(f"secrets merged ({len(keys_needed)} keys ensured, values not printed)")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    local = _read_file_secrets()
    c = paramiko.SSHClient()
    ssh_connect(c, role="auto")
    sftp = c.open_sftp()

    run(c, "mkdir -p /root/app/scripts /root/app/backend /root/app/docs/memory")

    uploads = [
        (ROOT / "scripts/stefan_morning_digest.py", "/root/app/scripts/stefan_morning_digest.py", False),
        (ROOT / "scripts/stefan_morning_digest.sh", "/root/app/scripts/stefan_morning_digest.sh", True),
        (ROOT / "app/backend/agency_mail.py", "/root/app/backend/agency_mail.py", False),
        (ROOT / "docs/memory/CURRENT.md", "/root/app/docs/memory/CURRENT.md", False),
    ]
    for src, rem, shell in uploads:
        if not src.is_file():
            print(f"SKIP missing {src}")
            continue
        data = src.read_bytes()
        data = normalize_lf(data) if shell else data.replace(b"\r\n", b"\n")
        with sftp.file(rem, "wb") as f:
            f.write(data)
        print(f"put {rem}")

    merge_secrets_on_remote(c, sftp, local)
    sftp.close()

    run(c, "chmod +x /root/app/scripts/stefan_morning_digest.sh")
    run(c, "sed -i 's/\\r$//' /root/app/scripts/stefan_morning_digest.sh")

    cron_line = "0 7 * * * /bin/bash /root/app/scripts/stefan_morning_digest.sh"
    run(
        c,
        f"(crontab -l 2>/dev/null | grep -v stefan_morning_digest; echo '{cron_line}') | crontab - "
        f"&& crontab -l | grep stefan",
    )

    # Fix digest: agency_mail looks for secrets — also symlink agency_email helper path
    # PYTHONPATH for import
    test_cmd = (
        "cd /root/app && PYTHONPATH=/root/app/backend "
        "/usr/bin/python3 /root/app/scripts/stefan_morning_digest.py"
    )
    if "--send" in sys.argv:
        run(c, test_cmd, t=90)
    else:
        run(c, test_cmd + " --dry-run", t=90)

    c.close()
    print("OK Stefan Digest · Cron 07:00 Europe/Berlin")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

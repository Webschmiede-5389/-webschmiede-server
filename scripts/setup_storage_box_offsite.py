#!/usr/bin/env python3
"""Create Hetzner Storage Box (bx11) + wire BACKUP_SFTP_* + test offsite upload.

Kosten: ca. 3,20 € netto / Monat. Christian: „Go on“ nach Offsite-Hinweis.
"""
from __future__ import annotations

import json
import secrets
import sys
import time
from pathlib import Path

import paramiko
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agency_config import ssh_connect, _read_file_secrets

BASE = "https://api.hetzner.com/v1"
BOX_NAME = "webschmiede-backups"


def merge_local_secrets(updates: dict[str, str]) -> None:
    path = ROOT / "deploy.secrets.local"
    existing: dict[str, str] = {}
    lines_out: list[str] = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                lines_out.append(line)
                continue
            k, v = s.split("=", 1)
            k = k.strip()
            if k in updates:
                lines_out.append(f"{k}={updates[k]}")
                existing[k] = updates[k]
            else:
                lines_out.append(line)
                existing[k] = v.strip()
    for k, v in updates.items():
        if k not in existing:
            lines_out.append(f"{k}={v}")
    path.write_text("\n".join(lines_out) + "\n", encoding="utf-8")
    print("deploy.secrets.local updated (values not printed)")


def merge_remote(role: str, updates: dict[str, str]) -> None:
    c = paramiko.SSHClient()
    ssh_connect(c, role=role)
    sftp = c.open_sftp()
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
    existing.update(updates)
    data = ("\n".join(f"{k}={v}" for k, v in existing.items()) + "\n").encode("utf-8")
    with sftp.file(remote, "w") as f:
        f.write(data)
    sftp.close()
    c.exec_command("chmod 600 /root/app/deploy.secrets.local", timeout=10)
    c.close()
    print(f"{role}: secrets merged")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    local = _read_file_secrets()
    token = (local.get("HETZNER_API_TOKEN") or "").strip()
    if not token:
        print("HETZNER_API_TOKEN fehlt")
        return 1
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Already have box?
    r = requests.get(f"{BASE}/storage_boxes", headers=headers, timeout=30)
    r.raise_for_status()
    boxes = r.json().get("storage_boxes") or []
    box = next((b for b in boxes if b.get("name") == BOX_NAME), None)
    password = secrets.token_urlsafe(24)

    if box:
        print(f"Storage Box existiert bereits id={box.get('id')}")
        # password unknown — keep existing BACKUP_SFTP if set
        if local.get("BACKUP_SFTP_HOST") and local.get("BACKUP_SFTP_PASS"):
            print("BACKUP_SFTP_* schon gesetzt — kein Reset")
            host = local["BACKUP_SFTP_HOST"]
            user = local["BACKUP_SFTP_USER"]
            password = local["BACKUP_SFTP_PASS"]
        else:
            print("Passwort reset via API…")
            rid = box["id"]
            rr = requests.post(
                f"{BASE}/storage_boxes/{rid}/actions/reset_password",
                headers=headers,
                json={"password": password},
                timeout=60,
            )
            print(f"reset_password HTTP {rr.status_code}")
            if rr.status_code not in (200, 201):
                print(rr.text[:400])
                return 1
            time.sleep(5)
            box = requests.get(f"{BASE}/storage_boxes/{rid}", headers=headers, timeout=30).json().get(
                "storage_box"
            )
            host = (box.get("server") or "") if isinstance(box.get("server"), str) else ""
            # username often in username field
            user = box.get("username") or ""
    else:
        print("Erstelle Storage Box bx11 in fsn1 …")
        body = {
            "name": BOX_NAME,
            "password": password,
            "location": "fsn1",
            "storage_box_type": "bx11",
            "access_settings": {
                "samba_enabled": False,
                "ssh_enabled": True,
                "webdav_enabled": False,
                "zfs_enabled": False,
                "reachable_externally": True,
            },
        }
        cr = requests.post(f"{BASE}/storage_boxes", headers=headers, json=body, timeout=120)
        print(f"create HTTP {cr.status_code}")
        if cr.status_code not in (200, 201):
            print(cr.text[:600])
            return 1
        data = cr.json()
        box = data.get("storage_box") or {}
        action = data.get("action") or {}
        aid = action.get("id")
        for _ in range(40):
            if not aid:
                break
            ar = requests.get(f"{BASE}/storage_boxes/actions/{aid}", headers=headers, timeout=30)
            st = (ar.json().get("action") or {}).get("status")
            print(f"  action status={st}")
            if st == "success":
                break
            if st == "error":
                print(ar.text[:400])
                return 1
            time.sleep(3)
        bid = box.get("id")
        box = requests.get(f"{BASE}/storage_boxes/{bid}", headers=headers, timeout=30).json().get(
            "storage_box"
        )
        user = (box or {}).get("username") or ""
        # server hostname
        host = ""
        if isinstance(box.get("server"), str):
            host = box["server"]
        elif isinstance(box.get("server"), dict):
            host = box["server"].get("name") or ""
        # often username.your-storagebox.de
        if not host and user:
            host = f"{user}.your-storagebox.de"

    print(f"Box id={box.get('id')} user={user} host={host} (password not printed)")

    # Enable SFTP if needed via update access
    bid = box.get("id")
    if bid:
        requests.put(
            f"{BASE}/storage_boxes/{bid}",
            headers=headers,
            json={
                "access_settings": {
                    "samba_enabled": False,
                    "ssh_enabled": True,
                    "webdav_enabled": False,
                    "zfs_enabled": False,
                    "reachable_externally": True,
                }
            },
            timeout=60,
        )

    if not host or not user:
        # refresh
        box = requests.get(f"{BASE}/storage_boxes/{bid}", headers=headers, timeout=30).json()[
            "storage_box"
        ]
        user = box.get("username") or user
        if isinstance(box.get("server"), str):
            host = box["server"]
        elif isinstance(box.get("server"), dict):
            host = box["server"].get("name") or host
        if not host and user:
            host = f"{user}.your-storagebox.de"
        print(f"refresh user={user} host={host}")

    updates = {
        "BACKUP_SFTP_HOST": host,
        "BACKUP_SFTP_USER": user,
        "BACKUP_SFTP_PASS": password,
        "BACKUP_SFTP_PATH": "backups",
    }
    merge_local_secrets(updates)
    for role in ("web", "auto"):
        # also keep encrypt passphrase
        full = dict(updates)
        if local.get("BACKUP_ENCRYPT_PASSPHRASE"):
            full["BACKUP_ENCRYPT_PASSPHRASE"] = local["BACKUP_ENCRYPT_PASSPHRASE"]
        # re-read after local merge
        local2 = _read_file_secrets()
        if local2.get("BACKUP_ENCRYPT_PASSPHRASE"):
            full["BACKUP_ENCRYPT_PASSPHRASE"] = local2["BACKUP_ENCRYPT_PASSPHRASE"]
        merge_remote(role, full)

    # mkdir backups on storage via sftp curl? try backup script
    print("Test-Backup + Offsite…")
    c = paramiko.SSHClient()
    ssh_connect(c, role="web")
    # ensure remote dir exists using curl sftp mkdir - may need lftp
    _, o, e = c.exec_command(
        "mkdir -p /root/app/backups/daily; "
        "/bin/bash /root/app/scripts/backup_agency.sh; "
        "tail -15 /var/log/snack-backup.log",
        timeout=180,
    )
    print((o.read() + e.read()).decode("utf-8", "replace")[-2000:])
    c.close()
    print("FERTIG Offsite (wenn Log 'offsite ok' zeigt)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

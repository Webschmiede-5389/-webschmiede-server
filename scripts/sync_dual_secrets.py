#!/usr/bin/env python3
"""Sync Dual-CX43 SSH/Backup-Keys in remote deploy.secrets.local (ohne Werte zu loggen)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paramiko
from agency_config import ssh_connect

KEYS_ALWAYS = (
    "WEB_HOST",
    "WEB_PASSWORD",
    "AUTO_HOST",
    "AUTO_PASSWORD",
    "SERVER_USER",
    "BACKUP_ENCRYPT_PASSPHRASE",
)


def _load_local() -> dict[str, str]:
    path = ROOT / "deploy.secrets.local"
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _parse_remote(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        raw = line.rstrip("\n\r")
        s = raw.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _merge_write(existing: str, updates: dict[str, str]) -> str:
    parsed = _parse_remote(existing)
    lines = existing.splitlines()
    seen: set[str] = set()
    out_lines: list[str] = []
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            out_lines.append(line.rstrip("\r"))
            continue
        k = s.split("=", 1)[0].strip()
        if k in updates:
            out_lines.append(f"{k}={updates[k]}")
            seen.add(k)
        else:
            out_lines.append(line.rstrip("\r"))
    for k, v in updates.items():
        if k not in seen:
            out_lines.append(f"{k}={v}")
    if out_lines and not out_lines[-1].endswith("\n"):
        return "\n".join(out_lines) + "\n"
    return "\n".join(out_lines) + ("\n" if out_lines else "")


def _sync_role(role: str, local: dict[str, str]) -> None:
    updates = {k: local[k] for k in KEYS_ALWAYS if local.get(k)}
    if role == "web":
        # Peer = auto
        if local.get("AUTO_HOST"):
            updates["BACKUP_PEER_HOST"] = local["AUTO_HOST"]
            updates["BACKUP_PEER_USER"] = local.get("SERVER_USER") or "root"
            if local.get("AUTO_PASSWORD"):
                updates["BACKUP_PEER_PASSWORD"] = local["AUTO_PASSWORD"]
            updates["BACKUP_PEER_PATH"] = "/root/app/backups/from-peer"
    else:
        if local.get("WEB_HOST"):
            updates["BACKUP_PEER_HOST"] = local["WEB_HOST"]
            updates["BACKUP_PEER_USER"] = local.get("SERVER_USER") or "root"
            if local.get("WEB_PASSWORD"):
                updates["BACKUP_PEER_PASSWORD"] = local["WEB_PASSWORD"]
            updates["BACKUP_PEER_PATH"] = "/root/app/backups/from-peer"

    client = paramiko.SSHClient()
    ssh_connect(client, timeout=20, banner_timeout=20, role=role)
    remote_path = "/root/app/deploy.secrets.local"
    _, o, _ = client.exec_command(f"test -f {remote_path} && cat {remote_path} || true")
    existing = o.read().decode("utf-8", errors="replace")
    before = set(_parse_remote(existing))
    merged = _merge_write(existing, updates)
    after = set(_parse_remote(merged))
    sftp = client.open_sftp()
    with sftp.file(remote_path, "w") as f:
        f.write(merged)
    sftp.close()
    # sshpass fuer Peer-Push
    _, o2, _ = client.exec_command(
        "command -v sshpass >/dev/null || (apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq sshpass); "
        "command -v sshpass && echo sshpass_ok || echo sshpass_missing"
    )
    pkg = o2.read().decode().strip()
    client.close()
    added = sorted(after - before)
    updated = sorted(k for k in updates if k in before)
    print(f"{role}: keys set={len(updates)} new={added or '-'} updated={updated or '-'} {pkg}")


def main() -> int:
    local = _load_local()
    need = ["WEB_HOST", "WEB_PASSWORD", "AUTO_HOST", "AUTO_PASSWORD"]
    missing = [k for k in need if not local.get(k)]
    if missing:
        print("FAIL local secrets fehlen:", ", ".join(missing))
        return 1
    _sync_role("web", local)
    _sync_role("auto", local)
    print("OK – keine Secret-Werte geloggt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fix deploy.secrets.local after voice rebuild overwrote AUTO_PASSWORD."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import requests
from agency_config import SECRETS_FILE, _read_file_secrets


def reset_pw(token: str, ip: str) -> str:
    r = requests.get(
        "https://api.hetzner.cloud/v1/servers",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    r.raise_for_status()
    sid = None
    for s in r.json().get("servers") or []:
        if (s.get("public_net") or {}).get("ipv4", {}).get("ip") == ip:
            sid = s["id"]
            break
    if not sid:
        raise SystemExit(f"Server {ip} nicht gefunden")
    rb = requests.post(
        f"https://api.hetzner.cloud/v1/servers/{sid}/actions/reset_password",
        headers={"Authorization": f"Bearer {token}"},
        json={},
        timeout=60,
    )
    rb.raise_for_status()
    return (rb.json().get("root_password") or "").strip()


def patch_secrets(updates: dict[str, str]) -> None:
    lines = []
    seen = set()
    text = SECRETS_FILE.read_text(encoding="utf-8") if SECRETS_FILE.exists() else ""
    for line in text.splitlines():
        k = line.split("=", 1)[0] if "=" in line else ""
        if k in updates:
            lines.append(f"{k}={updates[k]}")
            seen.add(k)
        else:
            lines.append(line)
    for k, v in updates.items():
        if k not in seen:
            lines.append(f"{k}={v}")
    SECRETS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    secrets = _read_file_secrets()
    token = secrets.get("HETZNER_API_TOKEN", "").strip()
    voice_pw = secrets.get("AUTO_PASSWORD", "")  # currently voice pw after mistake

    auto_pw = reset_pw(token, "88.198.170.156")
    patch_secrets({
        "AUTO_HOST": "88.198.170.156",
        "AUTO_PASSWORD": auto_pw,
        "VOICE_HOST": "167.233.150.230",
        "VOICE_PASSWORD": voice_pw,
    })
    print("OK Secrets: AUTO + VOICE getrennt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

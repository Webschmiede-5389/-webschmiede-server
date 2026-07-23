#!/usr/bin/env python3
"""Find Hetzner Cloud server by IP and rebuild with Ubuntu 24.04."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import requests
from agency_config import _read_file_secrets

IP = sys.argv[1] if len(sys.argv) > 1 else "88.198.170.156"


def main() -> int:
    token = _read_file_secrets().get("HETZNER_API_TOKEN", "").strip()
    if not token:
        print("HETZNER_API_TOKEN fehlt")
        return 1

    h = {"Authorization": f"Bearer {token}"}
    r = requests.get("https://api.hetzner.cloud/v1/servers", headers=h, timeout=30)
    r.raise_for_status()
    servers = r.json().get("servers") or []
    match = None
    for s in servers:
        for ip_obj in s.get("public_net", {}).get("ipv4", {}),:
            pass
        pub = s.get("public_net", {}).get("ipv4") or {}
        if pub.get("ip") == IP:
            match = s
            break
    if not match:
        print(f"Kein Cloud-Server mit IP {IP} gefunden. Liste:")
        for s in servers:
            ip = (s.get("public_net") or {}).get("ipv4", {}).get("ip", "?")
            print(f"  {s.get('id')} {s.get('name')} {ip}")
        return 1

    sid = match["id"]
    name = match.get("name")
    print(f"Gefunden: {name} (id={sid})")

    img_r = requests.get("https://api.hetzner.cloud/v1/images", headers=h, params={"type": "system"}, timeout=30)
    img_r.raise_for_status()
    image = None
    for img in img_r.json().get("images") or []:
        if img.get("name") == "ubuntu-24.04":
            image = img["id"]
            break
    if not image:
        print("ubuntu-24.04 image nicht gefunden")
        return 1

    if "--dry-run" in sys.argv:
        print(f"DRY RUN rebuild {name} with image {image}")
        return 0

    rb = requests.post(
        f"https://api.hetzner.cloud/v1/servers/{sid}/actions/rebuild",
        headers=h,
        json={"image": image},
        timeout=60,
    )
    if not rb.ok:
        print(rb.status_code, rb.text[:500])
        return 1
    root_pw = (rb.json().get("root_password") or "").strip()
    print("Rebuild gestartet.")
    if root_pw:
        print(f"Neues Root-Passwort (Hetzner): {root_pw}")
        print("(In deploy.secrets.local als AUTO_PASSWORD eintragen)")
    else:
        print("Passwort: wie in Hetzner Console / dein gesetztes Root-PW")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

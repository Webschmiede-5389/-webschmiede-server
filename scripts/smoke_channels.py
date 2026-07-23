#!/usr/bin/env python3
"""Smoke: Kunden-Kanäle API (SMS/WhatsApp/Voice)."""
import json
import sys

import paramiko

sys.path.insert(0, ".")
from agency_config import ssh_connect


def load_password(client):
    _, out, _ = client.exec_command(
        "grep '^AGENCY_ADMIN_PASSWORD=' /root/app/deploy.secrets.local 2>/dev/null | head -1 | cut -d= -f2-"
    )
    return out.read().decode("utf-8", errors="replace").strip()


def main():
    client = paramiko.SSHClient()
    ssh_connect(client, role="web")
    pw = load_password(client)
    if not pw:
        print("FAIL: kein Passwort")
        return 1

    # GET detail
    _, out, _ = client.exec_command(
        f"curl -s -H 'X-Agency-Password: {pw}' http://127.0.0.1:8000/api/agency/kunden/SHY001",
        timeout=20,
    )
    body = out.read().decode()
    data = json.loads(body)
    if "channels" not in data:
        print("FAIL: channels fehlen", list(data.keys())[:20])
        return 1
    ch = data["channels"]
    assert "sms" in ch and "whatsapp" in ch and "voice" in ch, ch.keys()
    print("OK GET channels:", list(ch.keys()))

    # PATCH nur non-destructive Feld (notes mit Marker, der idempotent ist)
    payload = json.dumps({
        "sms": {
            "notes": "go-live: SMS_API_KEY noch offen",
        },
    })
    # write payload to temp to avoid shell escaping hell
    sftp = client.open_sftp()
    with sftp.file("/tmp/ch_payload.json", "w") as f:
        f.write(payload)
    sftp.close()
    _, out, err = client.exec_command(
        f"curl -s -X PATCH -H 'Content-Type: application/json' -H 'X-Agency-Password: {pw}' "
        f"--data @/tmp/ch_payload.json http://127.0.0.1:8000/api/agency/kunden/SHY001/channels",
        timeout=20,
    )
    body = out.read().decode()
    errb = err.read().decode()
    if errb.strip():
        print("ERR:", errb[:200])
    data = json.loads(body)
    if not data.get("ok"):
        print("FAIL PATCH:", body[:300])
        return 1
    print("OK PATCH channels:", data.get("changed"), "sms notes=", (data.get("channels") or {}).get("sms", {}).get("notes"))
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

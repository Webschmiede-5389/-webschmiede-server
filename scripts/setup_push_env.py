#!/usr/bin/env python3
"""VAPID-Keys auf dem Server in /root/app/backend/.env eintragen (einmal)."""
from __future__ import annotations

import base64
import os
import sys

import paramiko
from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agency_config import ssh_connect

ENV_PATH = "/root/app/backend/.env"
MARKER = "VAPID_PUBLIC_KEY"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _vapid_lines() -> list[str]:
    v = Vapid()
    v.generate_keys()
    pub_bytes = v.public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    priv_pem = v.private_pem().decode("utf-8").replace("\n", "\\n")
    return [
        "PUSH_ENABLED=true",
        f"VAPID_PUBLIC_KEY={_b64url(pub_bytes)}",
        f'VAPID_PRIVATE_KEY="{priv_pem}"',
        "VAPID_CLAIMS_EMAIL=mailto:info@digitalehandwerkskunst.de",
    ]


def main() -> None:
    client = paramiko.SSHClient()
    ssh_connect(client, role="web")
    _, out, _ = client.exec_command(
        f"grep '^VAPID_PUBLIC_KEY=' {ENV_PATH} 2>/dev/null | head -1"
    )
    line = out.read().decode().strip()
    val = line.split("=", 1)[1].strip().strip('"') if "=" in line else ""
    if val:
        print("VAPID bereits in .env – nichts geändert.")
        client.close()
        return

    block = "\n# Web Push (Gäste)\n" + "\n".join(_vapid_lines()) + "\n"
    sftp = client.open_sftp()
    with sftp.open(ENV_PATH, "a") as f:
        f.write(block)
    sftp.close()
    client.exec_command("systemctl restart snack-api")
    print("VAPID-Keys eingetragen, snack-api neu gestartet.")
    client.close()


if __name__ == "__main__":
    main()

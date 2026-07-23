#!/usr/bin/env python3
"""VAPID-Schlüssel für Web Push erzeugen (einmal, in app/backend/.env)."""
from __future__ import annotations

import base64

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def main() -> None:
    v = Vapid()
    v.generate_keys()
    pub_bytes = v.public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    pub_b64 = b64url(pub_bytes)
    priv_pem = v.private_pem().decode("utf-8").replace("\n", "\\n")
    print("# In app/backend/.env eintragen (Private Key geheim halten):")
    print(f"VAPID_PUBLIC_KEY={pub_b64}")
    print(f'VAPID_PRIVATE_KEY="{priv_pem}"')
    print("VAPID_CLAIMS_EMAIL=mailto:info@digitalehandwerkskunst.de")
    print("PUSH_ENABLED=true")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Entfernt kundenspezifische Globals aus n8n (z. B. IVK BOOKKEEPER_EMAIL)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import paramiko
from agency_config import ssh_connect

N8N_ENV = "/opt/n8n/.env"
REMOVE_KEYS = ("BOOKKEEPER_EMAIL",)


def main():
    c = paramiko.SSHClient()
    ssh_connect(c)

    for key in REMOVE_KEYS:
        c.exec_command(f"sed -i '/^{key}=/d' {N8N_ENV}")

    c.exec_command("systemctl restart n8n")
    _, o, _ = c.exec_command(f"grep -E 'BOOKKEEPER|AGENCY_FROM' {N8N_ENV} || echo '(kein BOOKKEEPER mehr)'")
    print(o.read().decode())
    c.close()
    print("n8n: BOOKKEEPER_EMAIL entfernt (gehoert pro Kunde in kunden/*.json).")


if __name__ == "__main__":
    main()

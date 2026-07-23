#!/usr/bin/env python3
"""N8N_ORDER_WEBHOOK + Seminar-Webhook in Server-.env eintragen."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect

APP_ENV = "/root/app/backend/.env"
ORDER_WEBHOOK = "http://127.0.0.1:5678/webhook/new-order-shy001"
SEMINAR_WEBHOOK = "http://127.0.0.1:5678/webhook/seminar-registration"


def upsert(client, key, val):
    client.exec_command(
        f"grep -q '^{key}=' {APP_ENV} && "
        f"sed -i 's|^{key}=.*|{key}={val}|' {APP_ENV} || "
        f"echo '{key}={val}' >> {APP_ENV}"
    )


def main():
    c = paramiko.SSHClient()
    ssh_connect(c)
    upsert(c, "N8N_ORDER_WEBHOOK", ORDER_WEBHOOK)
    upsert(c, "N8N_SEMINAR_WEBHOOK", SEMINAR_WEBHOOK)
    c.exec_command("systemctl restart snack-api")
    _, o, _ = c.exec_command(f"grep N8N_ {APP_ENV}")
    print(o.read().decode())
    c.close()
    print("snack-api restarted")


if __name__ == "__main__":
    main()

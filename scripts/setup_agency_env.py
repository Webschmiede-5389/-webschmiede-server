#!/usr/bin/env python3
"""Set agency env vars on server (password, webhooks). No user input needed."""
import os
import secrets
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import load_secrets, ssh_connect, SECRETS_FILE

HOST = load_secrets()["SERVER_HOST"]
ENV_FILE = "/root/app/backend/.env"
WEBHOOK = f"http://{HOST}/n8n/webhook/seminar-registration"
CAL_URL = f"http://{HOST}/cal"


def load_local(key: str, default: str = "") -> str:
    if not SECRETS_FILE.exists():
        return default
    for line in SECRETS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return default


def run(client, cmd, timeout=30):
    _, out, err = client.exec_command(cmd, timeout=timeout)
    o = out.read().decode("utf-8", errors="replace").strip()
    e = err.read().decode("utf-8", errors="replace").strip()
    if o:
        print(o)
    if e and "WARNING" not in e.upper():
        print("ERR:", e[:300])
    return o


def set_env_var(client, key: str, value: str):
    escaped = value.replace("'", "'\"'\"'")
    run(
        client,
        f"grep -q '^{key}=' {ENV_FILE} 2>/dev/null && "
        f"sed -i 's|^{key}=.*|{key}={escaped}|' {ENV_FILE} || "
        f"echo '{key}={escaped}' >> {ENV_FILE}",
    )


def main():
    existing_pw = load_local("AGENCY_ADMIN_PASSWORD")
    agency_pw = existing_pw or secrets.token_urlsafe(18)
    owner_email = load_local("AGENCY_OWNER_EMAIL") or "info@digitalehandwerkskunst.de"

    client = paramiko.SSHClient()
    ssh_connect(client)

    print("=== Agency .env auf Server ===")
    set_env_var(client, "AGENCY_ADMIN_PASSWORD", agency_pw)
    set_env_var(client, "N8N_SEMINAR_WEBHOOK", WEBHOOK)
    set_env_var(client, "CALCOM_URL", CAL_URL)
    set_env_var(client, "AGENCY_OWNER_EMAIL", owner_email)

    print("\n=== snack-api neu starten ===")
    run(client, "systemctl restart snack-api")
    import time
    time.sleep(3)
    run(client, "systemctl is-active snack-api")

    cred_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agency-credentials.local.txt")
    with open(cred_path, "w", encoding="utf-8") as f:
        f.write("Webschmiede Agency — Zugangsdaten\n")
        f.write("=" * 40 + "\n\n")
        f.write(f"Agency Admin:  http://{HOST}/agency\n")
        f.write(f"Passwort:      {agency_pw}\n\n")
        f.write(f"Seminare:      http://{HOST}/seminare\n")
        f.write(f"Cal.com:       {CAL_URL} (nach setup_calcom.py)\n\n")
        f.write(f"n8n Webhook:   {WEBHOOK}\n")
        f.write(f"Owner E-Mail:  {owner_email}\n")
        f.write("\n(Datei ist gitignored — nicht committen.)\n")

    client.close()
    print(f"\nFERTIG — Credentials: {cred_path}")


if __name__ == "__main__":
    main()

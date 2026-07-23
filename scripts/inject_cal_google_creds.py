"""GOOGLE_API_CREDENTIALS + ALLOWED_HOSTNAMES in Cal.com setzen."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agency_config import ssh_connect
import paramiko

ROOT = Path(__file__).resolve().parents[1]
SECRETS = ROOT / "calcom-google.local.txt"
COMPOSE = "/opt/calcom/docker-compose.yml"
PUBLIC = "https://cal.digitalehandwerkskunst.de"
REDIRECT = f"{PUBLIC}/api/integrations/googlecalendar/callback"


def load_secrets() -> tuple[str, str]:
    if not SECRETS.exists():
        raise SystemExit(f"Fehlt: {SECRETS}")
    data = {}
    for line in SECRETS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip().strip('"').strip("'")
    cid = data.get("CLIENT_ID", "")
    secret = data.get("CLIENT_SECRET", "")
    if not cid or not secret or "DEIN" in cid.upper():
        raise SystemExit(
            "Bitte CLIENT_ID und CLIENT_SECRET in calcom-google.local.txt eintragen."
        )
    return cid, secret


def yaml_escape(s: str) -> str:
    # single-quoted YAML, escape '
    return "'" + s.replace("'", "''") + "'"


def main():
    cid, secret = load_secrets()
    creds = {
        "web": {
            "client_id": cid,
            "client_secret": secret,
            "redirect_uris": [
                REDIRECT,
                f"{PUBLIC}/api/auth/callback/google",
            ],
        }
    }
    creds_json = json.dumps(creds, separators=(",", ":"))

    c = paramiko.SSHClient()
    ssh_connect(c, timeout=25)
    sftp = c.open_sftp()
    with sftp.open(COMPOSE) as f:
        compose = f.read().decode()

    # remove old GOOGLE / ALLOWED lines under calcom environment
    lines = []
    in_cal_env = False
    for line in compose.splitlines():
        stripped = line.strip()
        if stripped.startswith("calcom:"):
            in_cal_env = False
        if in_cal_env and (
            stripped.startswith("GOOGLE_API_CREDENTIALS:")
            or stripped.startswith("GOOGLE_LOGIN_ENABLED:")
            or stripped.startswith("ALLOWED_HOSTNAMES:")
        ):
            continue
        lines.append(line)
        if stripped.startswith("environment:"):
            # mark next block — detect by indentation after services.calcom
            pass
        if "WEBAPP_URL:" in line and "cal.digitalehandwerkskunst.de" in line:
            in_cal_env = True  # after WEBAPP_URL we insert

    # rebuild properly: insert after WEBAPP_URL line
    out = []
    inserted = False
    for line in lines:
        out.append(line)
        if (not inserted) and line.strip().startswith("WEBAPP_URL:"):
            indent = line[: len(line) - len(line.lstrip())]
            out.append(f"{indent}ALLOWED_HOSTNAMES: '[\"cal.digitalehandwerkskunst.de\"]'")
            out.append(f"{indent}GOOGLE_LOGIN_ENABLED: 'true'")
            out.append(f"{indent}GOOGLE_API_CREDENTIALS: {yaml_escape(creds_json)}")
            inserted = True
    if not inserted:
        raise SystemExit("WEBAPP_URL nicht gefunden in compose")

    text = "\n".join(out) + "\n"
    with sftp.open(COMPOSE, "w") as f:
        f.write(text)
    sftp.close()

    _, o, e = c.exec_command(
        "cd /opt/calcom && docker compose up -d --force-recreate calcom", timeout=180
    )
    print((o.read() + e.read()).decode("utf-8", "replace")[-1500:].encode("ascii", "replace").decode())

    import time

    time.sleep(25)
    _, o, e = c.exec_command(
        "docker logs calcom-calcom-1 --tail 20 2>&1 | tr -cd '\\11\\12\\15\\40-\\176'; "
        "curl -sI -m 10 https://cal.digitalehandwerkskunst.de/auth/login | head -8",
        timeout=60,
    )
    print((o.read() + e.read()).decode("utf-8", "replace")[-2000:].encode("ascii", "replace").decode())
    c.close()
    print("OK: Google Credentials auf dem Server gesetzt.")
    print("Als Nächstes in Cal.com: Apps → Google Calendar → Install / Connect (ohne Key-UI).")


if __name__ == "__main__":
    main()

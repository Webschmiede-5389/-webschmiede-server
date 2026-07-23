#!/usr/bin/env python3
"""Force-activate Webschmiede platform n8n workflows and smoke-test webhooks."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paramiko
from agency_config import ssh_connect

ACTIVATE_PY = r"""
import sqlite3
c = sqlite3.connect("/opt/n8n/data/.n8n/database.sqlite")
print("=== before ===")
for wid, name, active in c.execute(
    "SELECT id, name, active FROM workflow_entity "
    "WHERE name LIKE '%Webschmiede%' OR name LIKE '%Support Ticket%' "
    "OR name LIKE '%Contract%' OR name LIKE '%Error Handler%' "
    "ORDER BY name"
):
    print(int(active or 0), wid, name)

keys = ("Support Ticket", "Contract Request", "Contract Completed", "Global Error Handler")
for wid, name, active in c.execute("SELECT id, name, active FROM workflow_entity"):
    if name.startswith("Webschmiede") and any(k in name for k in keys):
        c.execute("UPDATE workflow_entity SET active=1 WHERE id=?", (wid,))
        print("ON", wid, name)
c.commit()

print("=== after ===")
for wid, name, active in c.execute(
    "SELECT id, name, active FROM workflow_entity WHERE name LIKE 'Webschmiede%' ORDER BY name"
):
    print(int(active or 0), wid, name)
c.close()
"""


def safe_print(msg: str) -> None:
    sys.stdout.buffer.write((msg + "\n").encode("utf-8", errors="replace"))
    sys.stdout.flush()


def run(client, cmd: str, timeout: int = 120) -> str:
    _, o, e = client.exec_command(cmd, timeout=timeout)
    return (o.read() + e.read()).decode("utf-8", errors="replace").strip()


def post_webhook(path: str, payload: dict) -> tuple[int, str]:
    url = f"https://digitalehandwerkskunst.de/n8n/webhook/{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Origin": "https://digitalehandwerkskunst.de"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = resp.read().decode("utf-8", errors="replace")[:300]
            return resp.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        return exc.code, body
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc)


def main() -> int:
    auto = paramiko.SSHClient()
    ssh_connect(auto, timeout=25, banner_timeout=25, role="auto")
    sftp = auto.open_sftp()
    with sftp.file("/tmp/n8n_fix_ws.py", "w") as f:
        f.write(ACTIVATE_PY)
    sftp.close()
    safe_print(run(auto, "python3 /tmp/n8n_fix_ws.py"))
    safe_print(run(auto, "systemctl restart n8n && sleep 6 && systemctl is-active n8n"))
    auto.close()

    safe_print("\n=== webhook smoke ===")
    code, body = post_webhook(
        "support-ticket",
        {
            "subject": "Smoke-Test Support",
            "priority": "normal",
            "message": "Automatischer Smoke-Test – bitte ignorieren.",
            "name": "Smoke Test",
            "email": "smoke@digitalehandwerkskunst.de",
            "company": "Webschmiede",
            "source": "smoke-test",
            "submittedAt": "2026-07-22T12:00:00Z",
        },
    )
    safe_print(f"support-ticket -> HTTP {code}: {body}")

    code2, body2 = post_webhook(
        "contract-request",
        {
            "type": "contract-request",
            "selection": {
                "setupItems": ["Smoke"],
                "retainerItems": ["Smoke"],
                "setupTotal": 1,
                "retainerTotal": 1,
                "netTotal": 2,
                "vatAmount": 0.38,
                "grossTotal": 2.38,
            },
            "submittedAt": "2026-07-22T12:00:00Z",
            "source": "smoke-test",
        },
    )
    safe_print(f"contract-request -> HTTP {code2}: {body2}")
    return 0 if code in (200, 201) and code2 in (200, 201) else 1


if __name__ == "__main__":
    raise SystemExit(main())

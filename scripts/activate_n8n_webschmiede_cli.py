#!/usr/bin/env python3
"""Deduplicate Webschmiede webhook workflows and activate via n8n CLI."""
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

KEEP_NAMES = [
    "Webschmiede – Support Ticket",
    "Webschmiede – Contract Request (Kalkulator)",
    "Webschmiede – Contract Completed → CRM",
    "Webschmiede – Global Error Handler",
]

REMOTE_PY = r"""
import json, sqlite3, subprocess, os
os.chdir('/opt/n8n')
# load env for CLI
env = os.environ.copy()
for line in open('/opt/n8n/.env'):
    line=line.strip()
    if not line or line.startswith('#') or '=' not in line: continue
    k,v=line.split('=',1)
    env[k]=v.strip().strip('"').strip("'")
env['N8N_USER_FOLDER']='/opt/n8n/data'

c=sqlite3.connect('/opt/n8n/data/.n8n/database.sqlite')
# find keep targets: newest id per exact name
wanted = {
  'Webschmiede – Support Ticket',
  'Webschmiede – Contract Request (Kalkulator)',
  'Webschmiede – Contract Completed → CRM',
  'Webschmiede – Global Error Handler',
}
by_name={}
for wid,name,active,updated in c.execute(
  "SELECT id,name,active,updatedAt FROM workflow_entity ORDER BY updatedAt DESC"
):
    if name in wanted and name not in by_name:
        by_name[name]=wid
    elif name in wanted:
        # older duplicate -> deactivate in DB
        c.execute('UPDATE workflow_entity SET active=0 WHERE id=?', (wid,))
        print('DEACT_DUP', wid, name)
c.commit()
print('KEEP', json.dumps(by_name, ensure_ascii=False))

# Activate keepers via CLI (registers webhooks)
for name,wid in by_name.items():
    # first ensure active flag
    c.execute('UPDATE workflow_entity SET active=1 WHERE id=?', (wid,))
    c.commit()
    # n8n publish/update
    r=subprocess.run(
      ['n8n','update:workflow','--id='+str(wid),'--active=true'],
      cwd='/opt/n8n', env=env, capture_output=True, text=True, timeout=90
    )
    print('CLI', wid, name, 'rc', r.returncode)
    out=(r.stdout or '')+(r.stderr or '')
    print(out[:400].replace('\n',' | '))

# Fallback: try activate via sqlite + restart hint
print('DONE_CLI')
c.close()
"""


def safe_print(msg: str) -> None:
    sys.stdout.buffer.write((msg + "\n").encode("utf-8", errors="replace"))
    sys.stdout.flush()


def run(client, cmd: str, timeout: int = 180) -> str:
    _, o, e = client.exec_command(cmd, timeout=timeout)
    return (o.read() + e.read()).decode("utf-8", errors="replace").strip()


def post_webhook(path: str, payload: dict) -> tuple[int, str]:
    url = f"https://digitalehandwerkskunst.de/n8n/webhook/{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Origin": "https://digitalehandwerkskunst.de",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")[:400]
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")[:400]
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc)


def main() -> int:
    auto = paramiko.SSHClient()
    ssh_connect(auto, timeout=25, banner_timeout=25, role="auto")
    sftp = auto.open_sftp()
    with sftp.file("/tmp/n8n_activate_cli.py", "w") as f:
        f.write(REMOTE_PY)
    sftp.close()
    safe_print(run(auto, "python3 /tmp/n8n_activate_cli.py", timeout=240))
    safe_print(run(auto, "systemctl restart n8n && sleep 8 && systemctl is-active n8n"))

    # After restart, CLI activate again while n8n is up? Actually update:workflow may need n8n stopped
    # Try API activate with basic auth from env on server
    api_py = r"""
import json, os, sqlite3, urllib.request, base64, ssl
env={}
for line in open('/opt/n8n/.env'):
    line=line.strip()
    if not line or line.startswith('#') or '=' not in line: continue
    k,v=line.split('=',1)
    env[k]=v.strip().strip('"').strip("'")
user=env.get('N8N_BASIC_AUTH_USER','')
pw=env.get('N8N_BASIC_AUTH_PASSWORD','')
auth=base64.b64encode(f'{user}:{pw}'.encode()).decode()
c=sqlite3.connect('/opt/n8n/data/.n8n/database.sqlite')
wanted = (
  'Webschmiede – Support Ticket',
  'Webschmiede – Contract Request (Kalkulator)',
  'Webschmiede – Contract Completed → CRM',
)
ids=[]
seen=set()
for wid,name,active in c.execute('SELECT id,name,active FROM workflow_entity ORDER BY updatedAt DESC'):
    if name in wanted and name not in seen:
        ids.append((wid,name))
        seen.add(name)
    elif name in wanted:
        pass
c.close()
ctx=ssl.create_default_context()
for wid,name in ids:
    for base in ['http://127.0.0.1:5678','http://127.0.0.1:5678/n8n','http://127.0.0.1:5678/api/v1']:
        url=f'{base}/workflows/{wid}/activate'
        if '/api/v1' not in base and base.endswith('/n8n'):
            url=f'{base}/api/v1/workflows/{wid}/activate'
        elif base.endswith(':5678'):
            url=f'{base}/api/v1/workflows/{wid}/activate'
        req=urllib.request.Request(url, method='POST', headers={
            'Authorization': f'Basic {auth}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })
        try:
            with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
                print('API_OK', r.status, url, name)
                break
        except Exception as e:
            print('API_FAIL', url, type(e).__name__, str(e)[:120])
"""
    with sftp.file("/tmp/n8n_activate_api.py", "w") as f:
        f.write(api_py)
    # reopen sftp after close? need new sftp
    sftp = auto.open_sftp()
    with sftp.file("/tmp/n8n_activate_api.py", "w") as f:
        f.write(api_py)
    sftp.close()
    safe_print(run(auto, "python3 /tmp/n8n_activate_api.py", timeout=120))

    # local curl check
    safe_print(run(
        auto,
        "curl -s -o /tmp/wh.txt -w '%{http_code}' -X POST -H 'Content-Type: application/json' "
        "-d '{\"subject\":\"t\",\"priority\":\"normal\",\"message\":\"m\",\"name\":\"n\",\"email\":\"a@b.c\"}' "
        "http://127.0.0.1:5678/webhook/support-ticket; echo; head -c 300 /tmp/wh.txt; echo",
    ))
    auto.close()

    safe_print("\n=== public smoke ===")
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

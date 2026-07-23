#!/usr/bin/env python3
"""Patch nginx on web-01 via SSH jump from auto-01 (web often not reachable directly)."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paramiko
from agency_config import ssh_connect, target_secrets


def safe_print(msg: str) -> None:
    sys.stdout.buffer.write((msg + "\n").encode("utf-8", errors="replace"))
    sys.stdout.flush()


def run(client, cmd: str, timeout: int = 120) -> str:
    _, o, e = client.exec_command(cmd, timeout=timeout)
    return (o.read() + e.read()).decode("utf-8", errors="replace").strip()


REMOTE_ON_WEB = r'''
import pathlib, re, shutil, subprocess
path = pathlib.Path("/etc/nginx/sites-enabled/digitalehandwerkskunst.de")
text = path.read_text(encoding="utf-8")
print("webhook_before", text.count("location /n8n/webhook/"))
print("n8n_locs", text.count("location /n8n/ {"))
block = """
    # n8n production webhooks (registered at /webhook/ on n8n, not under N8N_PATH)
    location /n8n/webhook/ {
        proxy_pass         http://88.198.170.156:5678/webhook/;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_set_header   Connection "";
        proxy_read_timeout 120s;
    }
    location /n8n/webhook-test/ {
        proxy_pass         http://88.198.170.156:5678/webhook-test/;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_set_header   Connection "";
        proxy_read_timeout 120s;
    }
"""
# strip previous inserts
text2 = re.sub(
    r"\n\s*# n8n production webhooks.*?location /n8n/webhook-test/ \{.*?\n\s*\}\n",
    "\n",
    text,
    flags=re.S,
)
parts=[]; idx=0
for m in re.finditer(r"\n(\s*)location /n8n/ \{", text2):
    parts.append(text2[idx:m.start()]); parts.append("\n"+block); parts.append(text2[m.start():m.end()]); idx=m.end()
parts.append(text2[idx:])
new="".join(parts)
bak=pathlib.Path("/root/dh-nginx-webhook.bak")
shutil.copy2(path, bak)
path.write_text(new, encoding="utf-8")
r=subprocess.run(["nginx","-t"], capture_output=True, text=True)
print((r.stdout or "")+(r.stderr or ""))
if r.returncode!=0:
    shutil.copy2(bak, path); raise SystemExit("nginx -t failed")
subprocess.check_call(["systemctl","reload","nginx"])
print("webhook_after", path.read_text(encoding="utf-8").count("location /n8n/webhook/"))
print("RELOADED")
'''


def post(path: str, payload: dict) -> tuple[int, str]:
    url = f"https://digitalehandwerkskunst.de/n8n/webhook/{path}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Origin": "https://digitalehandwerkskunst.de"},
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
    web = target_secrets("web")
    web_host = web["SERVER_HOST"]
    web_pw = web["SERVER_PASSWORD"]
    user = web["SERVER_USER"]

    auto = paramiko.SSHClient()
    ssh_connect(auto, timeout=40, banner_timeout=40, role="auto")

    sftp = auto.open_sftp()
    with sftp.file("/tmp/nginx_wh_fix3.py", "w") as f:
        f.write(REMOTE_ON_WEB)
    with sftp.file("/tmp/jump_nginx_fix.py", "w") as f:
        f.write(
            "import paramiko\n"
            f"c=paramiko.SSHClient()\n"
            "c.set_missing_host_key_policy(paramiko.AutoAddPolicy())\n"
            f"c.connect({web_host!r}, username={user!r}, password={web_pw!r}, timeout=40, look_for_keys=False, allow_agent=False, banner_timeout=40)\n"
            "sftp=c.open_sftp()\n"
            "sftp.put('/tmp/nginx_wh_fix3.py','/tmp/nginx_wh_fix3.py')\n"
            "sftp.close()\n"
            "_,o,e=c.exec_command('python3 /tmp/nginx_wh_fix3.py', timeout=60)\n"
            "print((o.read()+e.read()).decode('utf-8','replace'))\n"
            "c.close()\n"
        )
    sftp.close()

    safe_print(run(auto, "python3 /tmp/jump_nginx_fix.py", timeout=120))
    auto.close()

    safe_print("\n=== smoke ===")
    ok = True
    for path, payload in [
        ("support-ticket", {"subject": "Smoke", "priority": "normal", "message": "ignore", "name": "S", "email": "smoke@digitalehandwerkskunst.de", "source": "smoke"}),
        ("contract-request", {"type": "contract-request", "selection": {"setupItems": ["S"], "retainerItems": ["S"], "setupTotal": 1, "retainerTotal": 1, "netTotal": 2, "vatAmount": 0.38, "grossTotal": 2.38}, "source": "smoke"}),
    ]:
        code, body = post(path, payload)
        safe_print(f"{path} -> {code}: {body}")
        if code not in (200, 201):
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

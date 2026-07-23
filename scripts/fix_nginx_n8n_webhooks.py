#!/usr/bin/env python3
"""Retry nginx webhook fix via auto jump to web if needed; diagnose path rewrite."""
from __future__ import annotations

import json
import sys
import time
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


def run(client, cmd: str, timeout: int = 90) -> str:
    _, o, e = client.exec_command(cmd, timeout=timeout)
    return (o.read() + e.read()).decode("utf-8", errors="replace").strip()


def connect(role: str, retries: int = 3):
    last = None
    for i in range(retries):
        try:
            c = paramiko.SSHClient()
            ssh_connect(c, timeout=40, banner_timeout=40, role=role)
            return c
        except Exception as exc:  # noqa: BLE001
            last = exc
            safe_print(f"retry {role} {i+1}: {exc}")
            time.sleep(3)
    raise last  # type: ignore[misc]


REMOTE_FIX = r'''
import pathlib, re, shutil, subprocess

path = pathlib.Path("/etc/nginx/sites-enabled/digitalehandwerkskunst.de")
text = path.read_text(encoding="utf-8")
print("SERVER_BLOCKS", text.count("server_name"))
print("LISTEN", [ln.strip() for ln in text.splitlines() if "listen" in ln])
print("WEBHOOK_LOCS", text.count("location /n8n/webhook/"))
print("N8N_LOCS", text.count("location /n8n/ {"))

# Ensure BOTH occurrences of location /n8n/ get webhook locations before them
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

# remove existing webhook locations to re-insert cleanly before every /n8n/
text2 = re.sub(
    r"\n\s*# n8n production webhooks.*?location /n8n/webhook-test/ \{.*?\n\s*\}\n",
    "\n",
    text,
    flags=re.S,
)

parts = []
idx = 0
for m in re.finditer(r"\n(\s*)location /n8n/ \{", text2):
    parts.append(text2[idx:m.start()])
    parts.append("\n" + block)
    parts.append(text2[m.start():m.end()])
    idx = m.end()
parts.append(text2[idx:])
new = "".join(parts)
if new == text2 and "location /n8n/webhook/" not in text2:
    raise SystemExit("no location /n8n/ found to patch")

bak = pathlib.Path("/root/dh-nginx-webhook.bak")
shutil.copy2(path, bak)
path.write_text(new, encoding="utf-8")
r = subprocess.run(["nginx", "-t"], capture_output=True, text=True)
print((r.stdout or "") + (r.stderr or ""))
if r.returncode != 0:
    shutil.copy2(bak, path)
    raise SystemExit("nginx -t failed")
subprocess.check_call(["systemctl", "reload", "nginx"])
print("RELOADED ok, webhook locs=", path.read_text(encoding="utf-8").count("location /n8n/webhook/"))
'''


def post(path: str, payload: dict) -> tuple[int, str]:
    url = f"https://digitalehandwerkskunst.de/n8n/webhook/{path}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
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
    web_host = target_secrets("web")["SERVER_HOST"]
    auto = connect("auto")
    # Diagnose from auto: what does public path look like locally
    safe_print(run(auto, "curl -s -o /tmp/t.txt -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d '{\"subject\":\"t\",\"priority\":\"normal\",\"message\":\"m\",\"name\":\"n\",\"email\":\"a@b.c\"}' http://127.0.0.1:5678/webhook/support-ticket; echo; head -c 200 /tmp/t.txt; echo"))

    # Try patch web via jump
    safe_print(f"jump patch web {web_host}")
    # upload script via auto? auto may not reach web SSH. Try direct web.
    auto.close()

    try:
        web = connect("web")
    except Exception:
        safe_print("web direct failed, try old")
        web = connect("old")

    sftp = web.open_sftp()
    with sftp.file("/tmp/nginx_wh_fix3.py", "w") as f:
        f.write(REMOTE_FIX)
    sftp.close()
    # only run if file exists
    out = run(web, "test -f /etc/nginx/sites-enabled/digitalehandwerkskunst.de && python3 /tmp/nginx_wh_fix3.py || echo NO_NGINX_SITE")
    safe_print(out)
    # dump relevant
    safe_print(run(web, "grep -n 'listen\\|server_name\\|location /n8n' /etc/nginx/sites-enabled/digitalehandwerkskunst.de 2>/dev/null | head -60 || true"))
    web.close()

    safe_print("\n=== smoke ===")
    for path, payload in [
        ("support-ticket", {"subject": "Smoke", "priority": "normal", "message": "ignore", "name": "S", "email": "smoke@digitalehandwerkskunst.de", "source": "smoke"}),
        ("contract-request", {"type": "contract-request", "selection": {"setupItems": ["S"], "retainerItems": ["S"], "setupTotal": 1, "retainerTotal": 1, "netTotal": 2, "vatAmount": 0.38, "grossTotal": 2.38}, "source": "smoke"}),
    ]:
        code, body = post(path, payload)
        safe_print(f"{path} -> {code}: {body}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

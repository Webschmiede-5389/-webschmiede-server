#!/usr/bin/env python3
"""Deploy fixed agency.html to both webroots."""
import os
import sys

import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency_config import ssh_connect

# sanity: no orphaned catch
html = open(os.path.join(ROOT, "app", "static", "agency.html"), encoding="utf-8").read()
assert "ok.classList.add('hidden');\n      try {\n        const d = await AgencyAuth.forgot" in html or "AgencyAuth.forgot(q)" in html
# ensure broken duplicate gone
bad = "    }\n        err.textContent = 'Reset fehlgeschlagen';"
assert bad not in html, "syntax break still present"

client = paramiko.SSHClient()
ssh_connect(client, timeout=60, banner_timeout=60, role="web")
sftp = client.open_sftp()
local = os.path.join(ROOT, "app", "static", "agency.html")
sftp.put(local, "/root/app/static/agency.html")
sftp.close()


def run(cmd: str) -> None:
    _, out, err = client.exec_command(cmd, timeout=60)
    text = (out.read() + err.read()).decode("utf-8", "replace").strip()
    if text:
        print(text)


run("cp /root/app/static/agency.html /var/www/snackhouse-mechernich/agency.html")
run("cp /root/app/static/agency.html /var/www/digitalehandwerkskunst/agency.html")
# nginx serves /agency from snackhouse root — confirm
run("grep -n 'async function doForgot' -A20 /var/www/snackhouse-mechernich/agency.html | head -25")
run("python3 -c \"import re; t=open('/var/www/snackhouse-mechernich/agency.html',encoding='utf-8',errors='replace').read(); print('orphan_reset_line', t.count(\\\"err.textContent = 'Reset fehlgeschlagen';\\\")); print('doLogin_count', t.count('async function doLogin'))\"")
client.close()
print("OK")

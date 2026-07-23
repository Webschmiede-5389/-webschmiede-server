#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency_config import ssh_connect

REMOTE = r'''
from pathlib import Path
import json, ssl, urllib.request

vals = {}
for p in (Path("/root/app/deploy.secrets.local"), Path("/root/app/backend/.env")):
    if p.exists():
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip()
pw = vals.get("AGENCY_ADMIN_PASSWORD", "")
body = json.dumps({"username": "christian", "password": pw}).encode()
ctx = ssl.create_default_context()

def hit(url):
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
            print(url, "->", r.status, r.read()[:120])
    except Exception as e:
        print(url, "->", type(e).__name__, getattr(e, "code", ""), str(e)[:120])
        if hasattr(e, "headers"):
            print("  allow=", e.headers.get("Allow"))
            print("  server=", e.headers.get("Server"))
        if hasattr(e, "read"):
            try:
                print("  body=", e.read()[:180])
            except Exception:
                pass

hit("https://digitalehandwerkskunst.de/api/agency/login")
hit("https://snackhouse-mechernich.de/api/agency/login")
hit("https://yassine.digitalehandwerkskunst.de/api/agency/login")

import os
for p in [
    "/var/www/digitalehandwerkskunst/agency-auth.js",
    "/var/www/snackhouse-mechernich/agency-auth.js",
    "/var/www/digitalehandwerkskunst/agency.html",
    "/var/www/snackhouse-mechernich/agency.html",
]:
    print(p, "exists" if os.path.isfile(p) else "MISSING", "size", os.path.getsize(p) if os.path.isfile(p) else 0)

# check if agency-auth on dhk has forgot throw
p = "/var/www/digitalehandwerkskunst/agency-auth.js"
if os.path.isfile(p):
    t = open(p, encoding="utf-8", errors="replace").read()
    print("dhk auth has throw on forgot", "throw new Error" in t)
    print("dhk auth login path", "/api/agency/login" in t)
p2 = "/var/www/snackhouse-mechernich/agency-auth.js"
if os.path.isfile(p2):
    t = open(p2, encoding="utf-8", errors="replace").read()
    print("shy auth has throw on forgot", "throw new Error" in t)
'''

c = paramiko.SSHClient()
ssh_connect(c, timeout=45, banner_timeout=45, role="web")
sftp = c.open_sftp()
with sftp.file("/tmp/test_https_login.py", "w") as f:
    f.write(REMOTE)
sftp.close()
_, o, e = c.exec_command("/root/app/venv/bin/python /tmp/test_https_login.py", timeout=60)
out = (o.read() + e.read()).decode("utf-8", "replace")
open(os.path.join(ROOT, "scripts", "_login_https_test.txt"), "w", encoding="utf-8").write(out)
print(out[:3000])
c.close()

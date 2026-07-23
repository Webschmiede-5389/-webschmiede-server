#!/usr/bin/env python3
import json
import re
import ssl
import urllib.request
from pathlib import Path

vals = {}
for line in Path(r"C:\Users\kumex\OneDrive\Desktop\Jarvis\Server\deploy.secrets.local").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        vals[k.strip()] = v.strip()
pw = vals["AGENCY_ADMIN_PASSWORD"]
ctx = ssl.create_default_context()

html = urllib.request.urlopen("https://digitalehandwerkskunst.de/agency", context=ctx, timeout=15).read().decode("utf-8", "replace")
print("scripts:", re.findall(r'src=["\']([^"\']+)["\']', html)[:10])
print("login-user", "login-user" in html)

body = json.dumps({"username": "christian", "password": pw}).encode()
req = urllib.request.Request(
    "https://digitalehandwerkskunst.de/api/agency/login",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
    d = json.loads(r.read().decode())
print("login_ok", d.get("success"), d.get("user", {}).get("username"))

body2 = json.dumps({"username": "christian", "password": "definitely-wrong"}).encode()
req2 = urllib.request.Request(
    "https://digitalehandwerkskunst.de/api/agency/login",
    data=body2,
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    urllib.request.urlopen(req2, context=ctx, timeout=15)
except Exception as e:
    print("wrong_pw_code", getattr(e, "code", None))

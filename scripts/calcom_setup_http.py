#!/usr/bin/env python3
"""Complete Cal.com first-admin setup via HTTP + set Do/Fr 14-18 in DB."""
from __future__ import annotations

import json
import os
import sys
import time

import paramiko
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency_config import ssh_connect

BASE = "https://cal.digitalehandwerkskunst.de"
setup = json.loads(
    open(os.path.join(ROOT, "scripts", "_cal_setup.json"), encoding="utf-8").read()
)

s = requests.Session()
s.headers.update(
    {
        "User-Agent": "Mozilla/5.0 WebschmiedeSetup/1.0",
        "Accept": "application/json, text/plain, */*",
    }
)

# Probe setup endpoints
for path in (
    "/api/auth/setup",
    "/api/auth/signup",
    "/api/trpc/viewer.admin.createUser",
):
    r = s.options(BASE + path, timeout=20)
    print("OPTIONS", path, r.status_code)

# GET setup page for cookies / csrf
r = s.get(BASE + "/auth/setup?step=1", timeout=30)
print("GET setup", r.status_code, "cookies", list(s.cookies.keys())[:10])

# Try common Cal.com setup payload
payloads = [
    (
        "POST /api/auth/setup",
        BASE + "/api/auth/setup",
        {
            "username": setup["username"],
            "email": setup["email"],
            "password": setup["password"],
            "full_name": setup["fullname"],
        },
    ),
    (
        "POST /api/auth/setup camel",
        BASE + "/api/auth/setup",
        {
            "username": setup["username"],
            "email": setup["email"],
            "password": setup["password"],
            "fullName": setup["fullname"],
            "name": setup["fullname"],
        },
    ),
]

for label, url, body in payloads:
    r = s.post(url, json=body, timeout=60)
    print(label, r.status_code, r.text[:500])
    if r.status_code in (200, 201):
        break

# Also try trpc batch style
trpc_url = BASE + "/api/trpc/viewer.auth.createFirstUser?batch=1"
r = s.post(
    trpc_url,
    json={
        "0": {
            "json": {
                "username": setup["username"],
                "email": setup["email"],
                "password": setup["password"],
                "fullName": setup["fullname"],
            }
        }
    },
    timeout=60,
)
print("trpc createFirstUser", r.status_code, r.text[:800])

# Inspect network from page source for hints
r = s.get(BASE + "/auth/setup?step=1", timeout=30)
idx = r.text.find("createFirst")
print("page has createFirst", idx)
# find api references
for needle in ("createFirstUser", "auth.setup", "/api/auth/setup", "viewer.admin"):
    if needle in r.text:
        print("found needle", needle)

print("DONE_HTTP")

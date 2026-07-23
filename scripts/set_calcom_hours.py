#!/usr/bin/env python3
"""Probe Cal.com API auth styles, then set Thu/Fri 14-18 Europe/Berlin."""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

vals = {}
for p in (Path(ROOT) / "deploy.secrets.local", Path(ROOT) / "app" / "backend" / ".env"):
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip()

KEY = (vals.get("CALCOM_API_KEY") or "").strip()
BASE = (vals.get("CALCOM_URL") or "https://cal.digitalehandwerkskunst.de").rstrip("/")

AVAIL = {
    "name": "Do–Fr Nachmittag",
    "timeZone": "Europe/Berlin",
    "isDefault": True,
    "availability": [
        {
            "days": ["Thursday", "Friday"],
            "startTime": "14:00",
            "endTime": "18:00",
        }
    ],
}


def req(method, path, body=None, headers=None, query=""):
    url = BASE + path + query
    data = None if body is None else json.dumps(body).encode()
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=25) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return resp.status, {"raw": raw[:300]}
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        return e.code, {"raw": raw[:400]}
    except Exception as e:
        return None, {"error": str(e)[:200]}


variants = [
    ("Bearer v2 schedules", "GET", "/api/v2/schedules", None, {"Authorization": f"Bearer {KEY}", "cal-api-version": "2024-06-11"}),
    ("Bearer v2 me", "GET", "/api/v2/me", None, {"Authorization": f"Bearer {KEY}", "cal-api-version": "2024-06-11"}),
    ("apiKey query v1 schedules", "GET", "/api/v1/schedules", None, {}, f"?apiKey={KEY}"),
    ("apiKey query v1 me", "GET", "/api/v1/me", None, {}, f"?apiKey={KEY}"),
    ("Bearer v1 schedules", "GET", "/api/v1/schedules", None, {"Authorization": f"Bearer {KEY}"}),
]

print("key_len", len(KEY), "base", BASE)
ok = None
for name, method, path, body, headers, *rest in [(a[0], a[1], a[2], a[3], a[4], a[5] if len(a) > 5 else "") for a in [
    ("Bearer v2 schedules", "GET", "/api/v2/schedules", None, {"Authorization": f"Bearer {KEY}", "cal-api-version": "2024-06-11"}, ""),
    ("Bearer v2 me", "GET", "/api/v2/me", None, {"Authorization": f"Bearer {KEY}", "cal-api-version": "2024-06-11"}, ""),
    ("apiKey query v1 schedules", "GET", "/api/v1/schedules", None, {}, f"?apiKey={KEY}"),
    ("apiKey query v1 me", "GET", "/api/v1/me", None, {}, f"?apiKey={KEY}"),
    ("Bearer v1 schedules", "GET", "/api/v1/schedules", None, {"Authorization": f"Bearer {KEY}"}, ""),
]]:
    q = rest[0] if rest else ""
    code, data = req(method, path, body, headers, q)
    preview = json.dumps(data, ensure_ascii=False)[:220]
    print(f"{name}: {code} {preview}")
    if code and code < 400:
        ok = (name, method, path, headers, q, data)

if not ok:
    print("NO_API_ACCESS")
    sys.exit(2)

name, method, path, headers, q, data = ok
print("USING", name)

# extract schedules list
schedules = []
if isinstance(data, dict):
    if isinstance(data.get("data"), list):
        schedules = data["data"]
    elif isinstance(data.get("schedules"), list):
        schedules = data["schedules"]
    elif isinstance(data.get("data"), dict) and isinstance(data["data"].get("schedules"), list):
        schedules = data["data"]["schedules"]

print("schedules_found", len(schedules))
if schedules:
    sid = schedules[0].get("id")
    print("update schedule", sid)
    if "v2" in name:
        code, resp = req(
            "PATCH",
            f"/api/v2/schedules/{sid}",
            AVAIL,
            headers,
            "",
        )
    else:
        # v1 often uses days as numbers 0=Sun..6=Sat; Thu=4 Fri=5
        body = {
            "name": AVAIL["name"],
            "timeZone": AVAIL["timeZone"],
            "availability": [
                {"days": [4, 5], "startTime": "14:00", "endTime": "18:00"}
            ],
        }
        code, resp = req("PATCH", f"/api/v1/schedules/{sid}", body, headers, q)
    print("PATCH", code, json.dumps(resp, ensure_ascii=False)[:400])
else:
    print("create schedule")
    if "v2" in name:
        code, resp = req("POST", "/api/v2/schedules", AVAIL, headers, "")
    else:
        body = {
            "name": AVAIL["name"],
            "timeZone": AVAIL["timeZone"],
            "availability": [
                {"days": [4, 5], "startTime": "14:00", "endTime": "18:00"}
            ],
        }
        code, resp = req("POST", "/api/v1/schedules", body, headers, q)
    print("POST", code, json.dumps(resp, ensure_ascii=False)[:400])

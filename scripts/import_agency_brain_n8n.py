#!/usr/bin/env python3
"""Import + aktiviert Agency-Hirn Workflows in n8n (Webhooks). Keine Secret-Werte loggen."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
CRED_FILE = ROOT / "n8n-credentials.local.txt"
FILES = [
    ROOT / "infra" / "n8n" / "workflow-agency-router.json",
    ROOT / "infra" / "n8n" / "agency-system" / "01-router.json",
    ROOT / "infra" / "n8n" / "agency-system" / "02-stefan.json",
    ROOT / "infra" / "n8n" / "agency-system" / "03-scout.json",
    ROOT / "infra" / "n8n" / "agency-system" / "09-nils.json",
    ROOT / "infra" / "n8n" / "workflow-b2b-baustoff.json",
]


def _creds() -> tuple[str, str, str]:
    url = user = password = ""
    for line in CRED_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("n8n URL:"):
            url = line.split(":", 1)[1].strip()
        elif line.startswith("n8n User:"):
            user = line.split(":", 1)[1].strip()
        elif line.startswith("n8n Password:"):
            password = line.split(":", 1)[1].strip()
    if not all((url, user, password)):
        raise SystemExit("n8n-credentials.local.txt unvollstaendig")
    return url.rstrip("/"), user, password


def _api_bases(public: str) -> list[str]:
    # n8n hinter /n8n/ Proxy
    bases = []
    if public.endswith("/n8n"):
        bases.append(f"{public}/api/v1")
    bases.append(f"{public.rstrip('/')}/api/v1")
    if "digitalehandwerkskunst.de" in public:
        bases.append("https://digitalehandwerkskunst.de/n8n/api/v1")
    # unique
    out = []
    for b in bases:
        if b not in out:
            out.append(b)
    return out


def main() -> int:
    public, user, password = _creds()
    auth = (user, password)
    base = None
    for candidate in _api_bases(public):
        try:
            r = requests.get(f"{candidate}/workflows", auth=auth, timeout=20)
            if r.status_code == 200:
                base = candidate
                break
            print("try", candidate, r.status_code)
        except Exception as e:
            print("try", candidate, type(e).__name__)
    if not base:
        print("FAIL: n8n API nicht erreichbar (Basic Auth). Evtl. API-Key in n8n noetig.")
        return 1
    print("API", base)

    existing = {}
    data = requests.get(f"{base}/workflows", auth=auth, timeout=30).json()
    items = data.get("data", data) if isinstance(data, dict) else data
    for w in items or []:
        existing[w.get("name")] = w.get("id")

    # Patch router workflow → brain endpoint
    brain_wf = ROOT / "infra" / "n8n" / "workflow-agency-brain.json"
    if not brain_wf.is_file():
        print("WARN brain workflow fehlt, skip")

    for path in FILES + ([brain_wf] if brain_wf.is_file() else []):
        if not path.is_file():
            print("SKIP missing", path.name)
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        name = raw.get("name") or path.stem
        payload = {
            "name": name,
            "nodes": raw.get("nodes", []),
            "connections": raw.get("connections", {}),
            "settings": raw.get("settings") or {"executionOrder": "v1"},
        }
        try:
            if name in existing:
                wid = existing[name]
                r = requests.put(f"{base}/workflows/{wid}", json=payload, auth=auth, timeout=60)
                action = "updated"
            else:
                r = requests.post(f"{base}/workflows", json=payload, auth=auth, timeout=60)
                action = "created"
            if r.status_code >= 400:
                print(f"FAIL {name}: {r.status_code} {r.text[:180]}")
                continue
            wid = (r.json() or {}).get("id") or existing.get(name)
            if wid:
                a = requests.post(f"{base}/workflows/{wid}/activate", auth=auth, timeout=30)
                print(f"OK {name} ({action}) id={wid} activate={a.status_code}")
            else:
                print(f"OK {name} ({action}) no id")
        except Exception as e:
            print(f"FAIL {name}: {e}")
    print("Fertig. Webhooks brauchen CRON_SECRET / AGENCY_ADMIN_PASSWORD in n8n Env.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

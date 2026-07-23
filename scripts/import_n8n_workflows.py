#!/usr/bin/env python3
"""Import infra/n8n/*.json workflows via n8n REST API (basic auth)."""
import json
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
N8N_DIR = ROOT / "infra" / "n8n"
CRED_FILE = ROOT / "n8n-credentials.local.txt"


def load_n8n_creds() -> tuple[str, str, str]:
    if not CRED_FILE.exists():
        raise SystemExit(f"Fehlt: {CRED_FILE} — zuerst setup_n8n.py oder verify_n8n.py")
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


def api_base(public_url: str) -> str:
    return f"{public_url}/api/v1"


def list_workflows(base: str, auth: tuple[str, str]) -> list[dict]:
    r = requests.get(f"{base}/workflows", auth=auth, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("data", data) if isinstance(data, dict) else data


def import_workflow(base: str, auth: tuple[str, str], path: Path) -> str:
    raw = json.loads(path.read_text(encoding="utf-8"))
    name = raw.get("name", path.stem)
    existing = {w.get("name"): w.get("id") for w in list_workflows(base, auth)}

    payload = {
        "name": name,
        "nodes": raw.get("nodes", []),
        "connections": raw.get("connections", {}),
        "settings": raw.get("settings", {}),
        "staticData": raw.get("staticData"),
    }
    if name in existing:
        wid = existing[name]
        r = requests.put(f"{base}/workflows/{wid}", json=payload, auth=auth, timeout=60)
        action = "updated"
    else:
        r = requests.post(f"{base}/workflows", json=payload, auth=auth, timeout=60)
        action = "created"
    if r.status_code >= 400:
        return f"FAIL {name}: {r.status_code} {r.text[:200]}"
    wid = r.json().get("id") or existing.get(name)
    # Activate workflow
    if wid:
        requests.post(f"{base}/workflows/{wid}/activate", auth=auth, timeout=30)
    return f"OK {name} ({action}, id={wid})"


def main():
    public_url, user, password = load_n8n_creds()
    base = api_base(public_url)
    auth = (user, password)

    files = sorted(N8N_DIR.glob("workflow-*.json"))
    if not files:
        raise SystemExit(f"Keine Workflows in {N8N_DIR}")

    print(f"n8n API: {base}\n")
    for f in files:
        try:
            print(import_workflow(base, auth, f))
        except Exception as e:
            print(f"FAIL {f.name}: {e}")

    print("\nHinweis: SMTP-Credentials in n8n UI fuer E-Mail-Nodes setzen.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Erlaubt SSH zwischen Dual-CX43 Peers (web <-> auto) in Firewall webschmiede-dual."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FW_ID = 11325352
HOME_IP = "92.209.219.236/32"


def _sec() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in (ROOT / "deploy.secrets.local").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


def main() -> int:
    sec = _sec()
    tok = sec.get("HETZNER_API_TOKEN") or ""
    web = (sec.get("WEB_HOST") or "").strip()
    auto = (sec.get("AUTO_HOST") or "").strip()
    if not tok or not web or not auto:
        print("FAIL: HETZNER_API_TOKEN / WEB_HOST / AUTO_HOST")
        return 1

    ssh_sources = sorted({HOME_IP, f"{web}/32", f"{auto}/32"})
    rules = [
        {
            "description": "SSH home + dual peers",
            "direction": "in",
            "protocol": "tcp",
            "port": "22",
            "source_ips": ssh_sources,
        },
        {
            "description": "HTTP",
            "direction": "in",
            "protocol": "tcp",
            "port": "80",
            "source_ips": ["0.0.0.0/0", "::/0"],
        },
        {
            "description": "HTTPS",
            "direction": "in",
            "protocol": "tcp",
            "port": "443",
            "source_ips": ["0.0.0.0/0", "::/0"],
        },
        {
            "description": "n8n from web",
            "direction": "in",
            "protocol": "tcp",
            "port": "5678",
            "source_ips": [f"{web}/32"],
        },
        {
            "description": "metrics from web",
            "direction": "in",
            "protocol": "tcp",
            "port": "8090",
            "source_ips": [f"{web}/32"],
        },
        {
            "description": "Ollama from web (Nils LLM)",
            "direction": "in",
            "protocol": "tcp",
            "port": "11434",
            "source_ips": [f"{web}/32"],
        },
        {
            "description": "ICMP",
            "direction": "in",
            "protocol": "icmp",
            "source_ips": ["0.0.0.0/0", "::/0"],
        },
    ]
    body = json.dumps({"rules": rules}).encode()
    req = urllib.request.Request(
        f"https://api.hetzner.cloud/v1/firewalls/{FW_ID}/actions/set_rules",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {tok}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print("FAIL", e.code, e.read()[:400])
        return 1
    action = (data.get("actions") or data.get("action") or {})
    if isinstance(action, list):
        action = action[0] if action else {}
    print("OK set_rules status=", action.get("status"), "ssh_sources=", ssh_sources)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

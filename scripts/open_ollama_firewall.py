#!/usr/bin/env python3
"""Allow web-01 → auto-01:11434 (Ollama) via Hetzner firewall if token present; else ufw on auto."""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paramiko
from agency_config import load_secrets, ssh_connect


def hetzner_open(sec: dict) -> bool:
    token = (sec.get("HETZNER_API_TOKEN") or "").strip()
    web = (sec.get("WEB_HOST") or "").strip()
    auto = (sec.get("AUTO_HOST") or "").strip()
    if not token or not web or not auto:
        print("hetzner_skip", "token_or_hosts_missing")
        return False
    # Find auto server id
    req = urllib.request.Request(
        "https://api.hetzner.cloud/v1/servers",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        servers = json.loads(r.read().decode()).get("servers") or []
    auto_id = None
    for s in servers:
        ip = (((s.get("public_net") or {}).get("ipv4") or {}).get("ip") or "")
        if ip == auto:
            auto_id = s.get("id")
            break
    if not auto_id:
        print("hetzner_skip", "auto_server_not_found")
        return False
    # List firewalls applied to auto
    req = urllib.request.Request(
        f"https://api.hetzner.cloud/v1/servers/{auto_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        fw_ids = [
            x.get("id")
            for x in (json.loads(r.read().decode()).get("server") or {}).get("public_net", {}).get("firewalls")
            or []
            if x.get("id")
        ]
    # Also try all firewalls
    if not fw_ids:
        req = urllib.request.Request(
            "https://api.hetzner.cloud/v1/firewalls",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            fw_ids = [f.get("id") for f in (json.loads(r.read().decode()).get("firewalls") or []) if f.get("id")]
    print("firewalls", fw_ids)
    # Prefer ufw on host if no easy FW API update — return False to fall through
    return False


def ufw_on_auto(sec: dict) -> None:
    web = (sec.get("WEB_HOST") or "").strip()
    client = paramiko.SSHClient()
    ssh_connect(client, timeout=15, banner_timeout=15, role="auto")
    cmd = f"""
set -e
WEB={web}
# Prefer iptables allow if ufw inactive
if command -v ufw >/dev/null 2>&1 && ufw status | grep -qi active; then
  ufw allow from "$WEB" to any port 11434 proto tcp comment 'ollama-from-web' || true
  ufw status | grep 11434 || true
  echo ufw_done
else
  # iptables insert if missing
  if ! iptables -C INPUT -p tcp -s "$WEB" --dport 11434 -j ACCEPT 2>/dev/null; then
    iptables -I INPUT -p tcp -s "$WEB" --dport 11434 -j ACCEPT
    echo iptables_added
  else
    echo iptables_exists
  fi
fi
# local smoke
curl -sf --max-time 3 http://127.0.0.1:11434/api/tags >/dev/null && echo ollama_local_ok
"""
    _, o, e = client.exec_command(cmd)
    print(o.read().decode(errors="replace"))
    err = e.read().decode(errors="replace")
    if err.strip():
        print(err[:300], file=sys.stderr)
    client.close()


def test_from_web(sec: dict) -> None:
    auto = (sec.get("AUTO_HOST") or "").strip()
    client = paramiko.SSHClient()
    ssh_connect(client, timeout=15, banner_timeout=15, role="web")
    cmd = f"""
curl -sf --max-time 10 http://{auto}:11434/api/tags | head -c 200 || echo REACH_FAIL
"""
    _, o, e = client.exec_command(cmd)
    print("from_web:", o.read().decode(errors="replace"))
    client.close()


def main() -> int:
    sec = load_secrets()
    hetzner_open(sec)
    ufw_on_auto(sec)
    test_from_web(sec)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

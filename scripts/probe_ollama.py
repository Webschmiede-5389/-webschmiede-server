#!/usr/bin/env python3
"""Find Ollama on dual servers (no secrets)."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import paramiko
from agency_config import ssh_connect, target_secrets

def probe(role: str) -> None:
    print(f"=== {role} ===")
    try:
        c = paramiko.SSHClient()
        ssh_connect(c, timeout=12, banner_timeout=12, role=role)
    except Exception as e:
        print("ssh_fail", type(e).__name__, str(e)[:100])
        return
    cmd = r"""
hostname
docker ps --format '{{.Names}}' 2>/dev/null | grep -iE 'ollama|voice' || true
ss -lnt 2>/dev/null | grep 11434 || netstat -lnt 2>/dev/null | grep 11434 || true
curl -sf --max-time 3 http://127.0.0.1:11434/api/tags | head -c 400 || echo 'ollama_local_fail'
# peer guesses
for h in 127.0.0.1 10.0.0.1 10.0.0.2; do
  code=$(curl -sf -o /tmp/otags -w '%{http_code}' --max-time 2 http://$h:11434/api/tags || echo 000)
  echo "probe_$h $code"
done
"""
    _, o, e = c.exec_command(cmd)
    print(o.read().decode(errors="replace"))
    err = e.read().decode(errors="replace")
    if err.strip():
        print("stderr", err[:200])
    c.close()

for role in ("web", "auto"):
    probe(role)

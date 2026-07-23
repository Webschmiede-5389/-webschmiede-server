#!/usr/bin/env python3
"""Test web→auto Ollama reachability."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import paramiko
from agency_config import ssh_connect, target_secrets

sec = target_secrets()
auto = (sec.get("AUTO_HOST") or "").strip()
print("auto_host_set", bool(auto))
# mask
if auto:
    parts = auto.split(".")
    print("auto_host_masked", ".".join(parts[:2] + ["x", "x"]) if len(parts) == 4 else auto[:6] + "…")

c = paramiko.SSHClient()
ssh_connect(c, timeout=12, banner_timeout=12, role="web")
cmd = f"""
AUTO={auto}
curl -sf --max-time 8 "http://$AUTO:11434/api/tags" | head -c 300 || echo FAIL
curl -sf --max-time 45 "http://$AUTO:11434/api/chat" -H 'Content-Type: application/json' -d '{{"model":"llama3.2:1b","stream":false,"messages":[{{"role":"user","content":"Sag nur: Nils bereit."}}]}}' | head -c 500 || echo CHAT_FAIL
"""
_, o, e = c.exec_command(cmd)
print(o.read().decode(errors="replace"))
print(e.read().decode(errors="replace")[:300])
c.close()

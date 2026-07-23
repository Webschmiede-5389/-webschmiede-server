#!/usr/bin/env python3
"""Check auto-01 RAM/disk and current Ollama models."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import paramiko
from agency_config import ssh_connect

c = paramiko.SSHClient()
ssh_connect(c, timeout=15, banner_timeout=15, role="auto")
cmd = r"""
free -h
df -h / | tail -1
nproc
docker stats --no-stream --format '{{.Name}} {{.MemUsage}}' 2>/dev/null | head -20
curl -sf http://127.0.0.1:11434/api/tags | python3 -c "import sys,json; d=json.load(sys.stdin); print('models', [m.get('name') for m in d.get('models') or []])"
"""
_, o, e = c.exec_command(cmd)
print(o.read().decode(errors="replace"))
c.close()

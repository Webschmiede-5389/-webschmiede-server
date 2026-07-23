#!/usr/bin/env python3
"""Längere Timeouts für /api/nils/* (Whisper/Vision/Chat)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agency_config import ssh_connect
import paramiko

REMOTE = r"""
from pathlib import Path
path = Path('/etc/nginx/sites-enabled/digitalehandwerkskunst.de')
t = path.read_text(encoding='utf-8', errors='replace')
marker = 'location /api/nils/'
snippet = '''
    location /api/nils/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 180s;
        proxy_send_timeout 180s;
        client_max_body_size 50m;
    }
'''
if marker in t:
    print('already present')
else:
    # vor generisches location /api/
    needle = 'location /api/'
    if needle not in t:
        raise SystemExit('no /api/ location')
    t = t.replace(needle, snippet + '\n    ' + needle, 1)
    path.write_text(t, encoding='utf-8')
    print('patched', path)
"""


def main() -> int:
    c = paramiko.SSHClient()
    ssh_connect(c, role="web")
    sftp = c.open_sftp()
    with sftp.file("/tmp/patch_nils_timeout.py", "w") as f:
        f.write(REMOTE)
    sftp.close()
    _, o, e = c.exec_command(
        "python3 /tmp/patch_nils_timeout.py && nginx -t && systemctl reload nginx",
        timeout=30,
    )
    print((o.read() + e.read()).decode("utf-8", "replace"))
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

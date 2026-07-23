#!/usr/bin/env python3
"""Clean URL /jay auf Agency-Nginx."""
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
if 'location = /jay' in t:
    print('already present')
else:
    snippet = '''
    location = /jay {
        try_files /jay.html =404;
    }
'''
    marker = 'location = /nils'
    if marker in t:
        t = t.replace(marker, snippet + '\n    ' + marker, 1)
    else:
        t = t.replace('location / {', snippet + '\n    location / {', 1)
    path.write_text(t, encoding='utf-8')
    print('patched')
"""


def main() -> int:
    c = paramiko.SSHClient()
    ssh_connect(c, role="web")
    sftp = c.open_sftp()
    with sftp.file("/tmp/patch_jay_nginx.py", "w") as f:
        f.write(REMOTE)
    sftp.close()
    _, o, e = c.exec_command(
        "python3 /tmp/patch_jay_nginx.py && nginx -t && systemctl reload nginx",
        timeout=30,
    )
    print((o.read() + e.read()).decode("utf-8", "replace"))
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

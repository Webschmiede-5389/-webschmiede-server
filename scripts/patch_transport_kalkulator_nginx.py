#!/usr/bin/env python3
"""Clean URL /transport-kalkulator nur auf Agency-Nginx (digitalehandwerkskunst.de)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agency_config import ssh_connect
import paramiko


def main() -> int:
    c = paramiko.SSHClient()
    ssh_connect(c, role="web")
    remote_script = r"""
from pathlib import Path
snippet = '''
    location = /transport-kalkulator {
        try_files /transport-kalkulator.html =404;
    }
'''
p = Path('/etc/nginx/sites-enabled/digitalehandwerkskunst.de')
if not p.exists():
    print('missing site file')
    raise SystemExit(1)
t = p.read_text(encoding='utf-8', errors='replace')
if 'location = /transport-kalkulator' in t:
    print('already present')
else:
    marker = 'location / {'
    if marker not in t:
        print('no location / { marker')
        raise SystemExit(2)
    t = t.replace(marker, snippet + '\n    ' + marker, 1)
    p.write_text(t, encoding='utf-8')
    print('patched', p)
"""
    sftp = c.open_sftp()
    with sftp.file("/tmp/patch_transport_nginx.py", "w") as f:
        f.write(remote_script)
    sftp.close()
    _, o, e = c.exec_command(
        "python3 /tmp/patch_transport_nginx.py && nginx -t && systemctl reload nginx",
        timeout=30,
    )
    print((o.read() + e.read()).decode("utf-8", "replace"))
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

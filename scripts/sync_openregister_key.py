#!/usr/bin/env python3
"""OPENREGISTER_API_KEY aus deploy.secrets.local auf den Server (.env) legen."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agency_config import load_secrets, ssh_connect
import paramiko


def main() -> int:
    sec = load_secrets()
    key = (sec.get("OPENREGISTER_API_KEY") or "").strip()
    if not key:
        print("FEHLT: OPENREGISTER_API_KEY in deploy.secrets.local")
        print("Datei:", ROOT / "deploy.secrets.local")
        return 1

    c = paramiko.SSHClient()
    ssh_connect(c, timeout=25, banner_timeout=25, role="web")
    sftp = c.open_sftp()
    remote_py = "/tmp/set_openregister_key.py"
    script = (
        "from pathlib import Path\n"
        f"key = {key!r}\n"
        "env = Path('/root/app/backend/.env')\n"
        "lines = env.read_text(errors='replace').splitlines() if env.exists() else []\n"
        "out, seen = [], False\n"
        "for line in lines:\n"
        "    if line.startswith('OPENREGISTER_API_KEY='):\n"
        "        out.append('OPENREGISTER_API_KEY=' + key)\n"
        "        seen = True\n"
        "    else:\n"
        "        out.append(line)\n"
        "if not seen:\n"
        "    out.append('OPENREGISTER_API_KEY=' + key)\n"
        "env.write_text('\\n'.join(out) + '\\n', encoding='utf-8')\n"
        "print('ok_set', len(key))\n"
    )
    with sftp.file(remote_py, "w") as f:
        f.write(script)
    sftp.close()

    _, o, e = c.exec_command(
        "python3 /tmp/set_openregister_key.py && "
        "systemctl restart snack-api && sleep 2 && systemctl is-active snack-api && "
        "cd /root/app/backend && PYTHONPATH=/root/app:/root/app/backend "
        "/root/app/venv/bin/python -c \"from akquise import register as r; print(r.readiness())\"",
        timeout=60,
    )
    print(o.read().decode(errors="replace"))
    err = e.read().decode(errors="replace")
    if err.strip():
        print(err[:800], file=sys.stderr)
    c.close()
    print("Fertig. Key liegt auf dem Server (nicht im Chat wiederholen).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

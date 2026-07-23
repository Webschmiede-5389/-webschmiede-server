#!/usr/bin/env python3
"""Voice-Gateway auf auto-01 aktualisieren (STT-Endpoint für Telegram)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paramiko
from agency_config import ssh_connect

LOCAL = ROOT / "infra" / "voice-demo" / "gateway" / "app.py"
REMOTE = "/root/infra/voice-demo/gateway/app.py"


def main() -> int:
    if not LOCAL.is_file():
        print("FAIL missing", LOCAL)
        return 1
    c = paramiko.SSHClient()
    ssh_connect(c, timeout=30, banner_timeout=30, role="auto")
    sftp = c.open_sftp()
    # Zielordner finden
    for candidate in (
        "/root/infra/voice-demo/gateway/app.py",
        "/opt/voice-demo/gateway/app.py",
        "/root/voice-demo/gateway/app.py",
    ):
        try:
            sftp.stat(str(Path(candidate).parent))
            remote = candidate
            break
        except OSError:
            remote = ""
    if not remote:
        # docker compose project dir
        _, o, _ = c.exec_command(
            "docker inspect voice-demo-gateway-1 --format '{{.Config.Labels}}' 2>/dev/null; "
            "find /root /opt /home -path '*/voice-demo/gateway/app.py' 2>/dev/null | head -3"
        )
        found = o.read().decode(errors="replace")
        print("search:", found[:500])
        lines = [ln.strip() for ln in found.splitlines() if ln.strip().endswith("app.py")]
        if not lines:
            print("FAIL: gateway app.py Pfad unbekannt")
            sftp.close()
            c.close()
            return 1
        remote = lines[0]
    print("upload ->", remote)
    sftp.put(str(LOCAL), remote)
    sftp.close()
    # Posix-Pfade, nicht Windows-Path (wir deployen auf Linux)
    compose_dir = remote.rsplit("/gateway/", 1)[0] if "/gateway/" in remote else "/root/app/infra/voice-demo"
    cmd = (
        f"cd {compose_dir} && "
        "docker compose build gateway && docker compose up -d gateway && "
        "sleep 4 && curl -sf http://127.0.0.1:8090/api/health; echo; "
        "python3 - <<'PY'\n"
        "import urllib.request\n"
        "print('stt_route_check')\n"
        "req=urllib.request.Request('http://127.0.0.1:8090/openapi.json')\n"
        "print(urllib.request.urlopen(req, timeout=10).read()[:200])\n"
        "PY"
    )
    _, o, e = c.exec_command(cmd, timeout=600)
    print(o.read().decode(errors="replace")[:2000])
    err = e.read().decode(errors="replace")
    if err.strip():
        print("stderr:", err[:800])
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

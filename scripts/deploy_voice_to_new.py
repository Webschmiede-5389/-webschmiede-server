#!/usr/bin/env python3
"""Install + start Voice-Demo on VOICE_HOST (Voice-01neu)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paramiko
from agency_config import ssh_connect

REMOTE = "/root/app"


def run(c: paramiko.SSHClient, cmd: str, timeout: int = 120) -> tuple[int, str]:
    print(f"$ {cmd[:90]}")
    _, out, err = c.exec_command(cmd, timeout=timeout)
    code = out.channel.recv_exit_status()
    text = (out.read() + err.read()).decode("utf-8", errors="replace")
    if text.strip():
        print(text[-1500:] if len(text) > 1500 else text)
    return code, text


def main() -> int:
    # 1) Upload + install (reuse remote_install logic via subprocess)
    import subprocess
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "remote_install_voice_demo.py")], cwd=str(ROOT))
    if r.returncode != 0:
        return r.returncode

    # 2) Start stack
    c = paramiko.SSHClient()
    ssh_connect(c, role="voice")
    code, _ = run(c, f"bash {REMOTE}/scripts/setup_voice_demo.sh", timeout=600)
    if code != 0:
        c.close()
        return code

    time.sleep(5)
    run(c, "curl -sf http://127.0.0.1:8090/api/health || echo health_fail")
    run(c, "docker compose -f /root/app/infra/voice-demo/docker-compose.yml ps")
    c.close()

    # 3) nginx + ufw
    subprocess.run([sys.executable, str(ROOT / "scripts" / "patch_voice_nginx.py")], cwd=str(ROOT), check=False)
    print("OK Voice-Demo auf Voice-01neu")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

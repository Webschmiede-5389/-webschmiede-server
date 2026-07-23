#!/usr/bin/env python3
"""Start Voice-Demo stack + patch nginx (install must be done)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agency_config import ssh_connect

REMOTE = "/root/app"
LOG = "/var/log/voice-setup.log"


def _stdout_safe() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def run(c: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str]:
    print(f"$ {cmd[:100]}")
    _, out, err = c.exec_command(cmd, timeout=timeout)
    code = out.channel.recv_exit_status()
    text = (out.read() + err.read()).decode("utf-8", "replace")
    if text.strip():
        print(text[-2000:] if len(text) > 2000 else text)
    return code, text


def main() -> int:
    _stdout_safe()
    c = paramiko.SSHClient()
    ssh_connect(c, role="voice")

    _, o, _ = c.exec_command(
        "test -f /root/app/infra/voice-demo/.install-complete && echo yes || echo no", timeout=15
    )
    if o.read().decode().strip() != "yes":
        print("Install-Marker fehlt. Erst: python scripts/remote_install_voice_demo.py")
        c.close()
        return 1

    code, _ = run(c, f"bash {REMOTE}/scripts/setup_voice_demo.sh > {LOG} 2>&1; echo EXIT:$?", timeout=900)
    _, o, _ = c.exec_command(f"tail -30 {LOG}", timeout=30)
    print(o.read().decode("utf-8", "replace"))
    if code != 0:
        c.close()
        return code

    time.sleep(3)
    run(c, "curl -sf http://127.0.0.1:8090/api/health || echo health_fail")
    run(c, "docker compose -f /root/app/infra/voice-demo/docker-compose.yml ps")
    c.close()

    import subprocess

    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "patch_voice_nginx.py")], cwd=str(ROOT))
    if r.returncode != 0:
        return r.returncode

    print("OK: Voice-Demo laeuft auf Voice-01neu")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

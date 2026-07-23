# -*- coding: utf-8 -*-
"""Upload Voice-Demo + Install-Skript auf CX33 und NUR installieren (kein Dauerstart).

Zielhost aus deploy.secrets.local:
  VOICE_HOST  oder  AUTO_HOST  oder  WEB_HOST

Aufruf:
  python scripts/remote_install_voice_demo.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agency_config import load_secrets, SECRETS_FILE  # noqa: E402


def _stdout_safe() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

LOCAL_DEMO = ROOT / "infra" / "voice-demo"
REMOTE_ROOT = "/root/app"
REMOTE_DEMO = f"{REMOTE_ROOT}/infra/voice-demo"


def pick_target(secrets: dict) -> tuple[str, str, str]:
    host = (
        os.environ.get("VOICE_HOST")
        or secrets.get("VOICE_HOST")
        or os.environ.get("AUTO_HOST")
        or secrets.get("AUTO_HOST")
        or secrets.get("WEB_HOST")
        or ""
    ).strip()
    if not host:
        raise SystemExit(
            "Kein CX33-Host in deploy.secrets.local.\n"
            "Bitte eintragen: VOICE_HOST=… oder AUTO_HOST=… oder WEB_HOST=…\n"
            f"Datei: {SECRETS_FILE}"
        )
    user = secrets.get("SERVER_USER", "root")
    password = (
        os.environ.get("VOICE_PASSWORD")
        or secrets.get("VOICE_PASSWORD")
        or os.environ.get("AUTO_PASSWORD")
        or secrets.get("AUTO_PASSWORD")
        or secrets.get("WEB_PASSWORD")
        or secrets.get("SERVER_PASSWORD")
        or ""
    )
    if not password:
        raise SystemExit("Passwort fehlt (VOICE_PASSWORD / SERVER_PASSWORD).")
    # Schutz: nicht versehentlich den 2-GB-Shop anfassen
    if host == secrets.get("SERVER_HOST", "167.233.211.170") and host == "167.233.211.170":
        raise SystemExit(
            f"Ziel {host} ist der kleine Shop-Server. "
            "VOICE_HOST/AUTO_HOST/WEB_HOST auf den CX33 setzen."
        )
    return host, user, password


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 120) -> str:
    print(f"$ {cmd[:100]}")
    _i, out, err = client.exec_command(cmd, timeout=timeout)
    # wait for exit
    exit_status = out.channel.recv_exit_status()
    text = (out.read() + err.read()).decode("utf-8", "replace")
    if text.strip():
        print(text[-2000:] if len(text) > 2000 else text)
    if exit_status != 0:
        raise RuntimeError(f"Befehl fehlgeschlagen ({exit_status}): {cmd}")
    return text


def put_tree(sftp: paramiko.SFTPClient, client: paramiko.SSHClient, local: Path, remote: str) -> int:
    run(client, f"mkdir -p '{remote}'", timeout=30)
    n = 0
    for path in sorted(local.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(local).as_posix()
        rpath = f"{remote}/{rel}"
        parent = "/".join(rpath.split("/")[:-1])
        run(client, f"mkdir -p '{parent}'", timeout=30)
        print("put", rel)
        sftp.put(str(path), rpath)
        n += 1
    return n


def main() -> None:
    _stdout_safe()
    secrets = load_secrets()
    # merge extra keys from file (load_secrets only returns host/user/password)
    extra: dict[str, str] = {}
    if SECRETS_FILE.exists():
        for line in SECRETS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            extra[k.strip()] = v.strip()
    secrets = {**extra, **secrets}

    host, user, password = pick_target(secrets)
    print(f"Ziel: {user}@{host} (Install only, kein Dauerstart)")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        host,
        username=user,
        password=password,
        timeout=25,
        look_for_keys=False,
        allow_agent=False,
        banner_timeout=25,
    )

    # RAM-Check vor Upload
    mem = run(client, "free -g | awk '/Mem:/ {print $2}'", timeout=30).strip()
    try:
        mem_gb = int(mem.splitlines()[-1].strip() or "0")
    except ValueError:
        mem_gb = 0
    print(f"Remote RAM (GB approx): {mem_gb}")
    if mem_gb < 7:
        client.close()
        raise SystemExit(f"Zu wenig RAM ({mem_gb} GB). CX33 erwartet.")

    sftp = client.open_sftp()
    run(client, f"mkdir -p {REMOTE_ROOT}/infra {REMOTE_ROOT}/scripts", timeout=30)
    n = put_tree(sftp, client, LOCAL_DEMO, REMOTE_DEMO)
    for name in ("install_voice_demo.sh", "setup_voice_demo.sh", "prefetch_voice_assets.sh"):
        local = ROOT / "scripts" / name
        if local.exists():
            remote = f"{REMOTE_ROOT}/scripts/{name}"
            sftp.put(str(local), remote)
            run(client, f"sed -i 's/\\r$//' '{remote}' && chmod +x '{remote}'", timeout=30)
            print("put script", name)
    sftp.close()
    print(f"Uploaded {n} voice-demo files")

    # Lange Installation: Log auf Server (Windows-Konsole + Unicode/Docker-Progress)
    print("Starte Install-Skript (kann 10–20 Min dauern)…")
    log = "/var/log/voice-install.log"
    cmd = f"bash {REMOTE_ROOT}/scripts/install_voice_demo.sh > {log} 2>&1; echo EXIT:$?"
    _i, out, err = client.exec_command(cmd, timeout=1800)
    text = (out.read() + err.read()).decode("utf-8", "replace")
    code_line = [l for l in text.splitlines() if l.startswith("EXIT:")]
    code = int(code_line[-1].split(":")[1]) if code_line else 1
    _, tail, _ = client.exec_command(f"tail -40 {log}", timeout=30)
    tail_text = tail.read().decode("utf-8", "replace")
    print(tail_text[-3000:] if len(tail_text) > 3000 else tail_text)
    client.close()
    if code != 0:
        raise SystemExit(f"Install fehlgeschlagen, exit={code}")
    print("\nOK: Voice-Demo installiert, Container gestoppt.")


if __name__ == "__main__":
    main()

"""Shell-Skripte sicher auf Linux deployen (LF, Syntax-Check)."""
from __future__ import annotations

from pathlib import Path


def shell_bytes(local_path: str | Path) -> bytes:
    data = Path(local_path).read_bytes()
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def upload_shell_script(sftp, local_path: str | Path, remote_path: str) -> None:
    with sftp.file(remote_path, "wb") as rf:
        rf.write(shell_bytes(local_path))


def verify_remote_shell(client, remote_path: str, timeout: int = 15) -> tuple[bool, str]:
    _, out, err = client.exec_command(f"bash -n {remote_path} 2>&1", timeout=timeout)
    msg = (out.read() + err.read()).decode("utf-8", errors="replace").strip()
    ok = not msg or "syntax error" not in msg.lower()
    return ok, msg


def strip_crlf_on_server(client, remote_path: str, timeout: int = 15) -> None:
    client.exec_command(f'sed -i "s/\\r$//" {remote_path}', timeout=timeout)[1].read()

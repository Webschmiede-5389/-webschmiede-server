"""Deploy index.html with /img/* paths (images already on WEBROOT)."""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paramiko
from agency_config import ssh_connect

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL = os.path.join(ROOT, "app", "static", "index.html")
REMOTE_APP = "/root/app/static/index.html"
WEBROOT = "/var/www/snackhouse-mechernich/index.html"


def sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    client = paramiko.SSHClient()
    ssh_connect(client, timeout=15, banner_timeout=15, role="web")
    sftp = client.open_sftp()
    print(f"Upload index.html -> {REMOTE_APP}")
    sftp.put(LOCAL, REMOTE_APP)
    sftp.close()
    _, stdout, _ = client.exec_command(f"cp {REMOTE_APP} {WEBROOT}")
    stdout.channel.recv_exit_status()
    _, stdout, _ = client.exec_command(f"sha256sum {WEBROOT} {REMOTE_APP}")
    print(stdout.read().decode())
    print("local sha256:", sha(LOCAL))
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

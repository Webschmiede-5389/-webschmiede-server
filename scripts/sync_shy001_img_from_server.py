"""Pull SHY001 /img assets from live WEBROOT into app/static/img (source of truth backup)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paramiko
from agency_config import ssh_connect

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_IMG = os.path.join(ROOT, "app", "static", "img")
REMOTE_IMG = "/var/www/snackhouse-mechernich/img"


def main() -> int:
    os.makedirs(LOCAL_IMG, exist_ok=True)
    client = paramiko.SSHClient()
    ssh_connect(client, timeout=15, banner_timeout=15, role="web")
    sftp = client.open_sftp()
    names = sorted(
        e.filename
        for e in sftp.listdir_attr(REMOTE_IMG)
        if not e.filename.startswith(".")
    )
    for name in names:
        remote = f"{REMOTE_IMG}/{name}"
        local = os.path.join(LOCAL_IMG, name)
        print(f"get {name}")
        sftp.get(remote, local)
    sftp.close()
    client.close()
    print(f"OK: {len(names)} files -> {LOCAL_IMG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

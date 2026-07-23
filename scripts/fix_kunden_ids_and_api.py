import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agency_config import ssh_connect
import paramiko

ROOT = Path(__file__).resolve().parents[1]
c = paramiko.SSHClient()
ssh_connect(c, timeout=25)


def run(cmd, timeout=60):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    print((o.read() + e.read()).decode("utf-8", "replace").encode("ascii", "replace").decode())


# where is gunicorn looking?
run("systemctl cat snack-api | tr -cd '\\11\\12\\15\\40-\\176' | head -40")
run("ls -la /root/app/kunden_ids.py /root/app/backend/kunden_ids.py 2>&1")

# upload to both locations to be safe
sftp = c.open_sftp()
local = str(ROOT / "kunden_ids.py")
for remote in ("/root/app/kunden_ids.py", "/root/app/backend/kunden_ids.py"):
    sftp.put(local, remote)
    print("uploaded", remote)
sftp.close()

run("systemctl restart snack-api; sleep 4; systemctl is-active snack-api; ss -lntp | grep 8000 || echo NO_8000")
run(
    "curl -s -w '\\n%{http_code}\\n' -H 'X-Agency-Password: LjACgh5K5rmrKEufk3_nBlMk' "
    "http://127.0.0.1:8000/api/agency/secrets | head -c 300; echo"
)
c.close()

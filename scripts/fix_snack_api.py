import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agency_config import ssh_connect
import paramiko

c = paramiko.SSHClient()
ssh_connect(c, timeout=25)


def run(cmd, timeout=90):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = (o.read() + e.read()).decode("utf-8", "replace")
    print(out.encode("ascii", "replace").decode())
    return out


run("systemctl is-active snack-api || true")
run("ss -lntp | grep 8000 || echo NO_8000")
run("journalctl -u snack-api -n 50 --no-pager | tr -cd '\\11\\12\\15\\40-\\176'")
print("=== restart ===")
run("systemctl restart snack-api; sleep 4; systemctl is-active snack-api; ss -lntp | grep 8000 || echo NO_8000")
run(
    "curl -s -o /tmp/sec.json -w '%{http_code}' -H 'X-Agency-Password: LjACgh5K5rmrKEufk3_nBlMk' "
    "http://127.0.0.1:8000/api/agency/secrets; echo; head -c 200 /tmp/sec.json; echo"
)
c.close()

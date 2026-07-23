"""Cal.com Diagnose: Port, Logs, Health."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agency_config import ssh_connect
import paramiko

c = paramiko.SSHClient()
ssh_connect(c, timeout=25, banner_timeout=25)


def run(cmd, timeout=90):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = (o.read() + e.read()).decode("utf-8", "replace")
    return out


cmds = [
    "docker ps -a --filter name=calcom",
    "ss -lntp | grep 3000 || netstat -lntp 2>/dev/null | grep 3000 || echo NO_LISTEN_3000",
    "curl -v -m 8 http://127.0.0.1:3000/ 2>&1 | tail -30",
    "docker inspect calcom-calcom-1 --format '{{.State.Status}} {{.State.Health.Status}} {{.State.ExitCode}}'",
    "docker logs calcom-calcom-1 --tail 60 2>&1 | tr -cd '\\11\\12\\15\\40-\\176' | tail -60",
    "docker logs calcom-database-1 --tail 20 2>&1 | tr -cd '\\11\\12\\15\\40-\\176'",
    "grep -A12 'location /cal' /etc/nginx/sites-available/snack-house",
]
for cmd in cmds:
    print("====", cmd[:70])
    print(run(cmd)[-2500:])
c.close()

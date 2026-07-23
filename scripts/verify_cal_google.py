import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agency_config import ssh_connect
import paramiko

c = paramiko.SSHClient()
ssh_connect(c, timeout=25)
time.sleep(20)


def run(cmd):
    _, o, e = c.exec_command(cmd, timeout=60)
    return (o.read() + e.read()).decode("utf-8", "replace")


print(run("grep -c GOOGLE_API_CREDENTIALS /opt/calcom/docker-compose.yml"))
print(run("grep ALLOWED_HOSTNAMES /opt/calcom/docker-compose.yml"))
print(run("curl -sI -m 15 https://cal.digitalehandwerkskunst.de/auth/login | head -12"))
print(run("docker logs calcom-calcom-1 --tail 6 2>&1 | tr -cd '\\11\\12\\15\\40-\\176'"))
c.close()

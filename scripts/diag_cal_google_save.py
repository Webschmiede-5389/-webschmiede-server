"""Cal.com Logs zu App-Keys / Google speichern."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agency_config import ssh_connect
import paramiko

c = paramiko.SSHClient()
ssh_connect(c, timeout=25)


def run(cmd, timeout=60):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    return (o.read() + e.read()).decode("utf-8", "replace")


print("=== compose env keys ===")
print(run("grep -E 'GOOGLE|WEBAPP|NEXTAUTH' /opt/calcom/docker-compose.yml"))
print("=== recent errors ===")
print(
    run(
        "docker logs calcom-calcom-1 --tail 120 2>&1 | tr -cd '\\11\\12\\15\\40-\\176' | grep -iE 'error|google|credential|key|app|401|403|500' | tail -40"
    )
)
print("=== health ===")
print(run("curl -sI -m 8 https://cal.digitalehandwerkskunst.de/apps | head -15"))
c.close()

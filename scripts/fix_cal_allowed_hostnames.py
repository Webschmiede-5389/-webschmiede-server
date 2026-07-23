"""Nur ALLOWED_HOSTNAMES setzen (ohne Google Secrets)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agency_config import ssh_connect
import paramiko

c = paramiko.SSHClient()
ssh_connect(c, timeout=25)
sftp = c.open_sftp()
with sftp.open("/opt/calcom/docker-compose.yml") as f:
    compose = f.read().decode()
lines = []
for line in compose.splitlines():
    if line.strip().startswith("ALLOWED_HOSTNAMES:"):
        continue
    lines.append(line)
    if line.strip().startswith("WEBAPP_URL:"):
        indent = line[: len(line) - len(line.lstrip())]
        lines.append(f'{indent}ALLOWED_HOSTNAMES: \'["cal.digitalehandwerkskunst.de"]\'')
text = "\n".join(lines) + "\n"
with sftp.open("/opt/calcom/docker-compose.yml", "w") as f:
    f.write(text)
sftp.close()
_, o, e = c.exec_command("cd /opt/calcom && docker compose up -d --force-recreate calcom", timeout=180)
print((o.read() + e.read()).decode("ascii", "replace")[-800:])
c.close()
print("ALLOWED_HOSTNAMES gesetzt")

"""Cal.com v6 Compose um DATABASE_DIRECT_URL erweitern und neu starten."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agency_config import ssh_connect
import paramiko

c = paramiko.SSHClient()
ssh_connect(c, timeout=25, banner_timeout=25)
sftp = c.open_sftp()
with sftp.open("/opt/calcom/docker-compose.yml") as f:
    compose = f.read().decode("utf-8")
print("BEFORE:\n", compose)

if "DATABASE_DIRECT_URL" not in compose:
    compose = compose.replace(
        "DATABASE_URL: postgresql://",
        "DATABASE_DIRECT_URL: postgresql://",
    )
    # That wrongly renamed DATABASE_URL - fix properly
    # re-read original and do correct insert
    with sftp.open("/opt/calcom/docker-compose.yml") as f:
        compose = f.read().decode("utf-8")

# Extract DATABASE_URL line and add DIRECT next to it
lines = []
for line in compose.splitlines():
    lines.append(line)
    if line.strip().startswith("DATABASE_URL:") and "DATABASE_DIRECT_URL" not in compose:
        indent = line[: len(line) - len(line.lstrip())]
        val = line.split(":", 1)[1].strip()
        lines.append(f"{indent}DATABASE_DIRECT_URL: {val}")

compose2 = "\n".join(lines) + "\n"
# Also ensure NEXTAUTH and other needed vars
if "DATABASE_DIRECT_URL" not in compose2:
    raise SystemExit("failed to add DIRECT")

with sftp.open("/opt/calcom/docker-compose.yml", "w") as f:
    f.write(compose2)
sftp.close()
print("AFTER:\n", compose2)


def run(cmd, timeout=300):
    print(">>>", cmd[:90])
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = (o.read() + e.read()).decode("utf-8", "replace")
    print(out[-2000:].encode("ascii", "replace").decode())
    return out


run("cd /opt/calcom && docker compose up -d --force-recreate calcom", timeout=180)
run("sleep 45")
run("docker logs calcom-calcom-1 --tail 40 2>&1 | tr -cd '\\11\\12\\15\\40-\\176'")
run("curl -sI -m 10 http://127.0.0.1:3000/ | head -10")
run("curl -sI -m 10 http://127.0.0.1/cal/ | head -10")
c.close()

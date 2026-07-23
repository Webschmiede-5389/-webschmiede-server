"""Cal.com auf öffentliche URL :3000 umstellen (ohne /cal Subpath-Konflikt)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agency_config import ssh_connect
import paramiko

PUBLIC = "http://167.233.211.170:3000"

c = paramiko.SSHClient()
ssh_connect(c, timeout=25, banner_timeout=25)
sftp = c.open_sftp()
with sftp.open("/opt/calcom/docker-compose.yml") as f:
    compose = f.read().decode()

compose = compose.replace('"127.0.0.1:3000:3000"', '"3000:3000"')
compose = compose.replace("127.0.0.1:3000:3000", "3000:3000")
for key in (
    "NEXT_PUBLIC_WEBAPP_URL",
    "NEXTAUTH_URL",
    "WEBAPP_URL",
):
    # replace value lines
    lines = []
    for line in compose.splitlines():
        if line.strip().startswith(f"{key}:"):
            indent = line[: len(line) - len(line.lstrip())]
            lines.append(f"{indent}{key}: {PUBLIC}")
        else:
            lines.append(line)
    compose = "\n".join(lines) + "\n"

with sftp.open("/opt/calcom/docker-compose.yml", "w") as f:
    f.write(compose)
sftp.close()
print(compose)


def run(cmd, timeout=180):
    print(">>>", cmd[:100])
    _, o, e = c.exec_command(cmd, timeout=timeout)
    print((o.read() + e.read()).decode("utf-8", "replace")[-1500:].encode("ascii", "replace").decode())


run("cd /opt/calcom && docker compose up -d --force-recreate calcom")
run("sleep 25")
# Firewall optional
run("ufw allow 3000/tcp 2>/dev/null || true; iptables -I INPUT -p tcp --dport 3000 -j ACCEPT 2>/dev/null || true")
run("curl -sI -m 10 http://127.0.0.1:3000/auth/setup | head -12")
run("docker logs calcom-calcom-1 --tail 15 2>&1 | tr -cd '\\11\\12\\15\\40-\\176'")

# Flask CALCOM_URL
run(
    f"grep -q '^CALCOM_URL=' /root/app/backend/.env && "
    f"sed -i 's|^CALCOM_URL=.*|CALCOM_URL={PUBLIC}|' /root/app/backend/.env || "
    f"echo 'CALCOM_URL={PUBLIC}' >> /root/app/backend/.env; "
    "systemctl restart snack-api; sleep 2; systemctl is-active snack-api"
)
c.close()

cred = Path(__file__).resolve().parents[1] / "calcom-credentials.local.txt"
if cred.exists():
    text = cred.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if not ln.startswith("Cal.com URL:")]
    lines.insert(0, f"Cal.com URL:     {PUBLIC}")
    lines.append("Setup: Browser neu öffnen → Admin anlegen.")
    lines.append("Passwort: mind. 15 Zeichen, Groß+Klein+Zahl.")
    cred.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("URL", PUBLIC)

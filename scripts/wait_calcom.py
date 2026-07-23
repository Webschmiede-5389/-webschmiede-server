"""Warten bis Cal.com antwortet, Logs bei Fehler."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agency_config import ssh_connect
import paramiko

c = paramiko.SSHClient()
ssh_connect(c, timeout=25, banner_timeout=25)


def run(cmd, timeout=120):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    return o.read().decode("utf-8", "replace"), e.read().decode("utf-8", "replace")


for i in range(24):
    out, _ = run("curl -s -o /dev/null -w '%{http_code}' -m 5 http://127.0.0.1:3000/ || echo fail")
    code = out.strip()
    print(f"try {i+1}: {code}")
    if code.isdigit() and code != "000" and "fail" not in code:
        if code not in ("502", "000"):
            print("UP", code)
            break
    time.sleep(15)
else:
    print("TIMEOUT")

ps, _ = run("docker compose -f /opt/calcom/docker-compose.yml ps")
print(ps)
logs, _ = run("docker logs calcom-calcom-1 --tail 80 2>&1")
print("=== LOGS ===")
print(logs[-4000:])
nginx, _ = run("grep -n 'location /cal' /etc/nginx/sites-available/snack-house || echo NO_CAL_LOC")
print("nginx:", nginx)
cal, _ = run("curl -sI -m 10 http://127.0.0.1/cal/ | head -12")
print("via nginx:", cal)
c.close()

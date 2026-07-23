"""Cal.com Status auf dem Server prüfen."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agency_config import ssh_connect
import paramiko

c = paramiko.SSHClient()
ssh_connect(c, timeout=25, banner_timeout=25)
cmds = [
    'docker ps --format "{{.Names}} {{.Status}}" 2>/dev/null | head -30',
    "ls -la /opt/calcom 2>/dev/null || echo NO_CALCOM_DIR",
    "curl -sI -m 8 http://127.0.0.1:3000/ 2>/dev/null | head -10 || echo NO_PORT_3000",
    "grep -n cal /etc/nginx/sites-available/snack-house 2>/dev/null | head -20 || echo NO_NGINX_CAL",
    "grep CALCOM /root/app/backend/.env 2>/dev/null || echo NO_CALCOM_ENV",
]
for cmd in cmds:
    print("====", cmd[:70])
    _, o, e = c.exec_command(cmd, timeout=90)
    print(o.read().decode("utf-8", "replace")[:2000])
    err = e.read().decode("utf-8", "replace")[:400]
    if err.strip():
        print("ERR", err[:400])
c.close()

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agency_config import ssh_connect
import paramiko

c = paramiko.SSHClient()
ssh_connect(c, timeout=20, role="web")
_, o, _ = c.exec_command(
    r"""
PW=$(grep -E '^AGENCY_ADMIN_PASSWORD=' /root/app/backend/.env | cut -d= -f2- | tr -d '\r')
systemctl is-active snack-api
curl -s -o /dev/null -w 'local:%{http_code}\n' -H "X-Agency-Password: $PW" http://127.0.0.1:8000/api/agency/secrets
curl -s -o /dev/null -w 'https:%{http_code}\n' -H "X-Agency-Password: $PW" https://digitalehandwerkskunst.de/api/agency/secrets
"""
)
print(o.read().decode())
c.close()

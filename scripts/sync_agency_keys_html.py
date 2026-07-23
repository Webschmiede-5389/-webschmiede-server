import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agency_config import ssh_connect
import paramiko

ROOT = Path(__file__).resolve().parents[1]
src = ROOT / "app" / "static" / "agency-setup.html"

c = paramiko.SSHClient()
ssh_connect(c, timeout=25, role="web")
sftp = c.open_sftp()
for remote in (
    "/var/www/digitalehandwerkskunst/agency-keys.html",
    "/var/www/snackhouse-mechernich/agency-keys.html",
    "/var/www/snackhouse-mechernich/agency-setup.html",
    "/root/app/static/agency-setup.html",
    "/root/app/static/agency-keys.html",
):
    sftp.put(str(src), remote)
    print("put", remote)
sftp.close()
_, o, _ = c.exec_command(
    r"""
PW=$(grep -E '^AGENCY_ADMIN_PASSWORD=' /root/app/backend/.env | cut -d= -f2- | tr -d '\r')
curl -s -o /dev/null -w '%{http_code}' -H "X-Agency-Password: $PW" http://127.0.0.1:8000/api/agency/secrets
"""
)
print("api", o.read().decode())
c.close()

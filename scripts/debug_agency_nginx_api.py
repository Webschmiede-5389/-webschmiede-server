"""Diagnose Agency nginx /api routing (kein Passwort hardcoden)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agency_config import ssh_connect
import paramiko

c = paramiko.SSHClient()
ssh_connect(c, timeout=25, role="web")


def run(cmd: str) -> str:
    _, o, e = c.exec_command(cmd, timeout=60)
    return (o.read() + e.read()).decode("utf-8", "replace")


print("=== agency nginx api ===")
print(
    run(
        "grep -n 'location /api\\|/agency-keys\\|proxy_pass' "
        "/etc/nginx/sites-enabled/digitalehandwerkskunst.de | head -40"
    )
)
print("=== snack-house api ===")
print(run("grep -n 'location /api' -A8 /etc/nginx/sites-enabled/snack-house | head -20"))
print("=== test via domains (PW aus Server-.env) ===")
# Passwort nur remote aus .env lesen, nie lokal hardcoden
print(
    run(
        r"""
PW=$(grep -E '^AGENCY_ADMIN_PASSWORD=' /root/app/backend/.env | cut -d= -f2- | tr -d '\r')
curl -s -o /tmp/a.json -w 'direct:%{http_code} ' -H "X-Agency-Password: $PW" http://127.0.0.1:8000/api/agency/secrets
curl -s -o /tmp/b.json -w 'agency-host:%{http_code} ' -H 'Host: digitalehandwerkskunst.de' -H "X-Agency-Password: $PW" http://127.0.0.1/api/agency/secrets
curl -s -o /tmp/c.json -w 'yassine-host:%{http_code}\n' -H 'Host: yassine.digitalehandwerkskunst.de' -H "X-Agency-Password: $PW" http://127.0.0.1/api/agency/secrets
echo -n 'body-a:'; head -c 80 /tmp/a.json; echo
echo -n 'body-b:'; head -c 80 /tmp/b.json; echo
echo -n 'body-c:'; head -c 80 /tmp/c.json; echo
"""
    )
)
c.close()

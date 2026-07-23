import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agency_config import ssh_connect
import paramiko

c = paramiko.SSHClient()
ssh_connect(c, timeout=20)
_, o, _ = c.exec_command(
    "systemctl is-active snack-api; "
    "curl -s -o /dev/null -w 'local:%{http_code}\\n' -H 'X-Agency-Password: LjACgh5K5rmrKEufk3_nBlMk' http://127.0.0.1:8000/api/agency/secrets; "
    "curl -s -o /dev/null -w 'https:%{http_code}\\n' -H 'X-Agency-Password: LjACgh5K5rmrKEufk3_nBlMk' https://digitalehandwerkskunst.de/api/agency/secrets"
)
print(o.read().decode())
c.close()

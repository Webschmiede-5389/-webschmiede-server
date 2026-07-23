import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agency_config import ssh_connect
import paramiko

c = paramiko.SSHClient()
ssh_connect(c, timeout=25)


def run(cmd):
    _, o, e = c.exec_command(cmd, timeout=60)
    return (o.read() + e.read()).decode("utf-8", "replace")


print("=== agency nginx api ===")
print(run("grep -n 'location /api\\|/agency-keys\\|proxy_pass' /etc/nginx/sites-enabled/digitalehandwerkskunst.de | head -40"))
print("=== snack-house api ===")
print(run("grep -n 'location /api' -A8 /etc/nginx/sites-enabled/snack-house | head -20"))
print("=== test via domains ===")
print(
    run(
        "curl -s -o /tmp/a.json -w 'ip:%{http_code} ' -H 'X-Agency-Password: LjACgh5K5rmrKEufk3_nBlMk' http://127.0.0.1:8000/api/agency/secrets; "
        "curl -s -o /tmp/b.json -w 'agency-host:%{http_code} ' -H 'Host: digitalehandwerkskunst.de' -H 'X-Agency-Password: LjACgh5K5rmrKEufk3_nBlMk' http://127.0.0.1/api/agency/secrets; "
        "curl -s -o /tmp/c.json -w 'snack-host:%{http_code}\\n' -H 'Host: 167.233.211.170' -H 'X-Agency-Password: LjACgh5K5rmrKEufk3_nBlMk' http://127.0.0.1/api/agency/secrets; "
        "echo -n 'body-a:'; head -c 120 /tmp/a.json; echo; echo -n 'body-b:'; head -c 120 /tmp/b.json; echo; echo -n 'body-c:'; head -c 120 /tmp/c.json; echo"
    )
)
c.close()

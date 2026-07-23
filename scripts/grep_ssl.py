import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect
client = paramiko.SSHClient()
ssh_connect(client)
_, out, _ = client.exec_command("nginx -T 2>/dev/null | grep -E 'listen 443|ssl_certificate'", timeout=30)
print(out.read().decode())
client.close()

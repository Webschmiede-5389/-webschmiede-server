import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect
client = paramiko.SSHClient()
ssh_connect(client)
_, out, _ = client.exec_command("cat /etc/nginx/sites-available/digitalehandwerkskunst.de", timeout=20)
print(out.read().decode("utf-8", errors="replace"))
client.close()

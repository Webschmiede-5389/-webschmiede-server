import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect
c = paramiko.SSHClient()
ssh_connect(c)
_, o, _ = c.exec_command("systemctl cat snack-api | head -20; which gunicorn; ls -la /root/app/backend/", timeout=30)
print(o.read().decode())
c.close()

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect
c = paramiko.SSHClient()
ssh_connect(c)
_, o, e = c.exec_command("/root/app/venv/bin/pip install -q stripe==11.4.0 && /root/app/venv/bin/python -c 'import stripe; print(stripe.VERSION)' && systemctl restart snack-api && systemctl is-active snack-api", timeout=180)
print(o.read().decode())
print(e.read().decode()[:400])
c.close()

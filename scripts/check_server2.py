import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect

c = paramiko.SSHClient()
ssh_connect(c, timeout=20, banner_timeout=20)


def run(cmd, t=30):
    _, o, e = c.exec_command(cmd, timeout=t)
    print(o.read().decode("utf-8", errors="replace")[:1200])
    err = e.read().decode("utf-8", errors="replace").strip()
    if err:
        print("ERR:", err[:400])


run("node -v 2>/dev/null; npm -v 2>/dev/null; which node")
c.close()

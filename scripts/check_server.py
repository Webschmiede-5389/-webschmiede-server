import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect

c = paramiko.SSHClient()
ssh_connect(c, timeout=20, banner_timeout=20)


def run(cmd, timeout=30):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace").strip()
    err = e.read().decode("utf-8", errors="replace").strip()
    print(">>>", cmd[:75])
    if out:
        print(out[:1000])
    if err:
        print("ERR:", err[:500])
    print("---")


run("docker --version 2>/dev/null || echo NO_DOCKER")
run("node -v 2>/dev/null; npm -v 2>/dev/null; which node")
run("free -h | head -2")
run("systemctl is-active snack-api")
c.close()

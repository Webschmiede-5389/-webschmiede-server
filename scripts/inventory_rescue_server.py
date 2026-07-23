#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko

HOST = sys.argv[1] if len(sys.argv) > 1 else "167.233.150.230"
PW = os.environ.get("NEW_SERVER_PASSWORD", "")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username="root", password=PW, timeout=25, look_for_keys=False, allow_agent=False)
for cmd in ["hostname", "uname -a", "df -h / | tail -1", "free -h | head -2", "which installimage 2>/dev/null || echo no-installimage"]:
    _, o, _ = c.exec_command(cmd)
    print(cmd + ":", o.read().decode().strip().replace("\n", " | "))
c.close()

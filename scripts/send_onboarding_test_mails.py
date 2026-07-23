#!/usr/bin/env python3
"""Test: Onboarding-Mails für SHY001 an zwei Adressen."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paramiko
from agency_config import ssh_connect

RECIPIENTS = [
    "safer@psamarketing.de",
    "christian.kummetat@gmail.com",
]

REMOTE = r'''
import sys
sys.path.insert(0, "/root/app/backend")
sys.path.insert(0, "/root/app")
os_chdir = __import__("os").chdir
os_chdir("/root/app/backend")
from dotenv import load_dotenv
load_dotenv("/root/app/backend/.env")
import agency_cockpit as cockpit

recipients = __RECIPIENTS__
results = []
for to in recipients:
    try:
        r = cockpit.send_onboarding("SHY001", email=to)
        results.append({"to": to, "ok": True, "result": r})
        print("OK", to)
    except Exception as e:
        results.append({"to": to, "ok": False, "error": str(e)[:200]})
        print("FAIL", to, e)
'''

c = paramiko.SSHClient()
ssh_connect(c)
script = REMOTE.replace("__RECIPIENTS__", repr(RECIPIENTS))
sftp = c.open_sftp()
with sftp.file("/tmp/send_onboarding_test.py", "w") as f:
    f.write(script)
sftp.close()
_, out, err = c.exec_command(
    "cd /root/app/backend && /root/app/venv/bin/python3 /tmp/send_onboarding_test.py",
    timeout=60,
)
print(out.read().decode(errors="replace"))
e = err.read().decode(errors="replace")
if e.strip():
    print("ERR:", e[:500])
c.close()

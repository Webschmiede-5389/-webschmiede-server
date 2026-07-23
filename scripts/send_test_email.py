"""Send agency SMTP test mail to a given address."""
import json
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect

TO = sys.argv[1] if len(sys.argv) > 1 else "christian.kummetat@gmail.com"
CRED = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agency-credentials.local.txt")

pw = ""
for line in open(CRED, encoding="utf-8"):
    if line.strip().startswith("Passwort:"):
        pw = line.split(":", 1)[1].strip()
        break

client = paramiko.SSHClient()
ssh_connect(client)

script = f"""import json, urllib.request
body = json.dumps({{"to": {TO!r}}}).encode()
req = urllib.request.Request(
    "http://127.0.0.1:8000/api/agency/secrets/test/smtp",
    data=body,
    headers={{
        "Content-Type": "application/json",
        "X-Agency-Password": {pw!r},
    }},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=45) as r:
        print(r.read().decode())
except Exception as e:
    err = e.read().decode() if hasattr(e, "read") else str(e)
    print(json.dumps({{"ok": False, "error": err}}))
"""

sftp = client.open_sftp()
with sftp.open("/tmp/send_test_mail.py", "w") as f:
    f.write(script)
sftp.close()

_, out, _ = client.exec_command("/root/app/venv/bin/python /tmp/send_test_mail.py", timeout=60)
time.sleep(2)
result = out.read().decode().strip()
print(result)
client.exec_command("rm -f /tmp/send_test_mail.py")
client.close()

data = json.loads(result)
if not data.get("ok"):
    raise SystemExit(1)

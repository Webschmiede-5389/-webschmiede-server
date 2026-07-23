"""Show which agency secret fields are set (no values)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect

KEYS = [
    ("AGENCY_ADMIN_PASSWORD", "Agency Login (/agency, /agency-setup)"),
    ("AGENCY_SMTP_USER", "E-Mail-Adresse (SMTP Login)"),
    ("AGENCY_SMTP_PASS", "E-Mail-Passwort (Postfach)"),
    ("AGENCY_SMTP_HOST", "SMTP Server"),
    ("AGENCY_OWNER_EMAIL", "Deine Agency-E-Mail"),
]

client = paramiko.SSHClient()
ssh_connect(client)
_, o, _ = client.exec_command("cat /root/app/deploy.secrets.local 2>/dev/null")
text = o.read().decode("utf-8")
vals = {}
for line in text.splitlines():
    s = line.strip()
    if s and not s.startswith("#") and "=" in s:
        k, v = line.split("=", 1)
        vals[k.strip()] = v.strip()

print("deploy.secrets.local auf dem Server:\n")
for key, label in KEYS:
    v = vals.get(key, "")
    if v:
        print(f"  [gesetzt]  {label}")
        print(f"             ({key})")
    else:
        print(f"  [leer]     {label}")
        print(f"             ({key})")
client.close()

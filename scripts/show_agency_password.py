"""Show where AGENCY_ADMIN_PASSWORD is set (masked)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect, SECRETS_FILE

def mask(v):
    if not v:
        return "(leer)"
    if len(v) <= 4:
        return "****"
    return v[:2] + "…" + v[-2:]

# Local deploy.secrets.local
local = ""
if SECRETS_FILE.exists():
    for line in SECRETS_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("AGENCY_ADMIN_PASSWORD="):
            local = line.split("=", 1)[1].strip()
            break
print(f"Lokal deploy.secrets.local: {mask(local) if local else 'nicht gesetzt'}")

client = paramiko.SSHClient()
ssh_connect(client)
for path in ("/root/app/backend/.env", "/root/app/deploy.secrets.local"):
    _, o, _ = client.exec_command(f"grep '^AGENCY_ADMIN_PASSWORD=' {path} 2>/dev/null || true")
    val = o.read().decode().strip()
    if val and "=" in val:
        pw = val.split("=", 1)[1].strip().strip('"').strip("'")
        print(f"Server {path}: {mask(pw)}")
    else:
        print(f"Server {path}: nicht gesetzt")

_, o, _ = client.exec_command("grep '^ADMIN_PASSWORD=' /root/app/backend/.env 2>/dev/null || true")
fb = o.read().decode().strip()
if fb and "=" in fb:
    pw = fb.split("=", 1)[1].strip().strip('"').strip("'")
    print(f"Server Fallback ADMIN_PASSWORD (.env): {mask(pw)}")
client.close()

"""Places-Key vom Server in lokale deploy.secrets.local spiegeln."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agency_config import ssh_connect
import paramiko

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "deploy.secrets.local"

c = paramiko.SSHClient()
ssh_connect(c, timeout=20)
_, o, _ = c.exec_command(
    "grep '^GOOGLE_PLACES_API_KEY=' /root/app/deploy.secrets.local"
)
line = o.read().decode().strip()
c.close()
if not line.startswith("GOOGLE_PLACES_API_KEY="):
    raise SystemExit("Key nicht auf Server")

key_line = line
if not LOCAL.exists():
    LOCAL.write_text("# synced\n" + key_line + "\n", encoding="utf-8")
else:
    lines = LOCAL.read_text(encoding="utf-8").splitlines()
    out = []
    found = False
    for ln in lines:
        if ln.startswith("GOOGLE_PLACES_API_KEY="):
            out.append(key_line)
            found = True
        else:
            out.append(ln)
    if not found:
        out.append(key_line)
    LOCAL.write_text("\n".join(out) + "\n", encoding="utf-8")
print("local deploy.secrets.local updated")

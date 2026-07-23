"""Vergleicht lokales vs. Server Agency-Passwort (ohne Klartext-Ausgabe)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agency_config import load_secrets, ssh_connect
import paramiko

local = load_secrets()
local_agency = local.get("AGENCY_ADMIN_PASSWORD", "")
local_admin = local.get("ADMIN_PASSWORD", "")

c = paramiko.SSHClient()
ssh_connect(c, timeout=25, role="web")
_, o, _ = c.exec_command(
    "grep -E '^AGENCY_ADMIN_PASSWORD=|^ADMIN_PASSWORD=' /root/app/backend/.env 2>/dev/null"
)
env = o.read().decode().strip()
server = {}
for line in env.splitlines():
    if "=" in line:
        k, v = line.split("=", 1)
        server[k] = v.strip().strip('"').strip("'")

print("local AGENCY set:", bool(local_agency), "len", len(local_agency) if local_agency else 0)
print("local ADMIN set:", bool(local_admin), "len", len(local_admin) if local_admin else 0)
print("server keys:", list(server.keys()))
print("server AGENCY len:", len(server.get("AGENCY_ADMIN_PASSWORD", "") or ""))
print("server ADMIN len:", len(server.get("ADMIN_PASSWORD", "") or ""))
print("agency match local file:", server.get("AGENCY_ADMIN_PASSWORD") == local_agency)
print("agency==admin on server:", server.get("AGENCY_ADMIN_PASSWORD") == server.get("ADMIN_PASSWORD"))
effective = server.get("AGENCY_ADMIN_PASSWORD") or server.get("ADMIN_PASSWORD") or ""
print("effective len:", len(effective))

_, o, _ = c.exec_command(
    r"""
PW=$(grep -E '^AGENCY_ADMIN_PASSWORD=' /root/app/backend/.env | cut -d= -f2- | tr -d '\r')
curl -s -o /dev/null -w '%{http_code}' -H "X-Agency-Password: $PW" http://127.0.0.1:8000/api/agency/secrets/schema; echo
curl -s -o /dev/null -w '%{http_code}' -H 'X-Agency-Password: wrong' http://127.0.0.1:8000/api/agency/secrets/schema; echo
"""
)
print("api probe:", o.read().decode())
c.close()

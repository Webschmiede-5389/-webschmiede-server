"""Prüfen ob Google Places Key auf dem Server liegt und funktioniert."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agency_config import ssh_connect
import paramiko

c = paramiko.SSHClient()
ssh_connect(c, timeout=25)


def run(cmd, timeout=60):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    return (o.read() + e.read()).decode("utf-8", "replace")


# Masked status via API
print("=== API status ===")
print(
    run(
        "curl -s -H 'X-Agency-Password: LjACgh5K5rmrKEufk3_nBlMk' "
        "http://127.0.0.1:8000/api/agency/secrets "
        "| python3 -c \"import sys,json; d=json.load(sys.stdin); "
        "items={i['key']:i for i in d.get('items',[])}; "
        "g=items.get('GOOGLE_PLACES_API_KEY',{}); "
        "print('set=', g.get('set'), 'masked=', g.get('masked'), 'display=', g.get('display'))\""
    )
)

print("=== env / secrets files ===")
print(
    run(
        "grep -E '^GOOGLE_PLACES_API_KEY=' /root/app/backend/.env 2>/dev/null | sed 's/=.*/=***SET***/' || echo 'backend .env: missing'; "
        "grep -E '^GOOGLE_PLACES_API_KEY=' /root/deploy.secrets.local 2>/dev/null | sed 's/=.*/=***SET***/' || echo 'deploy.secrets.local: missing'; "
        "ls -la /root/deploy.secrets.local /root/app/deploy.secrets.local 2>&1 | head -5"
    )
)

print("=== test endpoint ===")
print(
    run(
        "curl -s -X POST -H 'Content-Type: application/json' "
        "-H 'X-Agency-Password: LjACgh5K5rmrKEufk3_nBlMk' "
        "http://127.0.0.1:8000/api/agency/secrets/test/google_places"
    )
)
c.close()

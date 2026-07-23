"""GOOGLE_PLACES_API_KEY von Server-Secrets in .env spiegeln."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agency_config import ssh_connect
import paramiko

c = paramiko.SSHClient()
ssh_connect(c, timeout=25)
cmd = r"""
python3 - <<'PY'
from pathlib import Path
sec = Path('/root/app/deploy.secrets.local')
env = Path('/root/app/backend/.env')
vals = {}
for line in sec.read_text().splitlines():
    if '=' in line and not line.strip().startswith('#'):
        k,v = line.split('=',1)
        vals[k.strip()] = v.strip()
key = vals.get('GOOGLE_PLACES_API_KEY','')
print('key_len', len(key))
if not key:
    raise SystemExit('no key')
lines = env.read_text().splitlines() if env.exists() else []
out=[]; found=False
for line in lines:
    if line.startswith('GOOGLE_PLACES_API_KEY='):
        out.append(f'GOOGLE_PLACES_API_KEY={key}'); found=True
    else:
        out.append(line)
if not found:
    out.append(f'GOOGLE_PLACES_API_KEY={key}')
env.write_text('\n'.join(out)+'\n')
print('env updated')
PY
systemctl restart snack-api
sleep 3
systemctl is-active snack-api
curl -s -X POST -H 'Content-Type: application/json' -H 'X-Agency-Password: LjACgh5K5rmrKEufk3_nBlMk' http://127.0.0.1:8000/api/agency/secrets/test/google_places
"""
_, o, e = c.exec_command(cmd, timeout=60)
print((o.read() + e.read()).decode("utf-8", "replace").encode("ascii", "replace").decode())
c.close()

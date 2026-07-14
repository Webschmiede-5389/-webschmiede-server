import paramiko
from agency_config import ssh_connect

client = paramiko.SSHClient()
ssh_connect(client, timeout=15, banner_timeout=15)

def run(cmd):
    _, out, err = client.exec_command(cmd, timeout=15)
    o = out.read().decode('utf-8', errors='replace').strip()
    e = err.read().decode('utf-8', errors='replace').strip()
    if o:
        print(o)
    if e:
        print('ERR:', e[:300])
    return o

env = '/root/app/backend/.env'
for line in [
    'GHL_ENABLED=false',
    'SMS_ENABLED=false',
    'SMS_API_KEY=',
    'SMS_SENDER=SnackHouse',
    'OWNER_PHONE=',
    'SHOP_NAME=Snack House Yassine',
    'SHOP_PHONE=024433088966',
]:
    key = line.split('=')[0]
    run(f"grep -q '^{key}=' {env} || echo '{line}' >> {env}")

run(f"sed -i 's/^GHL_ENABLED=.*/GHL_ENABLED=false/' {env}")
run('systemctl restart snack-api')
import time
time.sleep(2)
run('systemctl is-active snack-api')
run('curl -s http://localhost:8000/api/admin/contacts -H "X-Admin-Password: snackhouse2026"')
client.close()

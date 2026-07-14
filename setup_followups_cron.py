"""Deploy follow-up cron + CRON_SECRET on server."""
import paramiko, secrets, os
from agency_config import ssh_connect

LOCAL_SCRIPT = os.path.join(os.path.dirname(__file__), 'app', 'scripts', 'run_followups.sh')
ENV_PATH = '/root/app/backend/.env'

client = paramiko.SSHClient()
ssh_connect(client, timeout=15, banner_timeout=15)

def run(cmd, timeout=20):
    _, out, err = client.exec_command(cmd, timeout=timeout)
    o = out.read().decode('utf-8', errors='replace').strip()
    e = err.read().decode('utf-8', errors='replace').strip()
    if o: print(o)
    if e: print('ERR:', e[:300])
    return o

run('mkdir -p /root/app/scripts')
sftp = client.open_sftp()
sftp.put(LOCAL_SCRIPT, '/root/app/scripts/run_followups.sh')
sftp.close()
run('sed -i "s/\\r$//" /root/app/scripts/run_followups.sh')
run('chmod +x /root/app/scripts/run_followups.sh')

secret = secrets.token_hex(24)
run(f"grep -q '^CRON_SECRET=' {ENV_PATH} || echo 'CRON_SECRET={secret}' >> {ENV_PATH}")
if 'CRON_SECRET=' in run(f'grep CRON_SECRET {ENV_PATH}'):
    pass
run(f"grep -q '^GOOGLE_REVIEW_URL=' {ENV_PATH} || echo 'GOOGLE_REVIEW_URL=' >> {ENV_PATH}")

# Cron: täglich 10:00
cron_line = '0 10 * * * /bin/bash /root/app/scripts/run_followups.sh >> /var/log/snack-followups.log 2>&1'
run(f'(crontab -l 2>/dev/null | grep -v run_followups.sh; echo "{cron_line}") | crontab -')
run('crontab -l | grep followups || true')
run('systemctl restart snack-api', timeout=45)
import time; time.sleep(3)
run('systemctl is-active snack-api', timeout=15)
client.close()
print('Follow-up Cron eingerichtet.')

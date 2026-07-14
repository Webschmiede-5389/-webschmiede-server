import paramiko
from agency_config import ssh_connect
c = paramiko.SSHClient()
ssh_connect(c, timeout=15, banner_timeout=15)

def run(cmd):
    _, o, e = c.exec_command(cmd, timeout=30)
    out = o.read().decode().strip()
    err = e.read().decode().strip()
    print('CMD:', cmd[:80])
    if out:
        print('OUT:', out)
    if err:
        print('ERR:', err[:500])
    print('---')

run('systemctl is-active snack-api')
run('bash -x /root/app/scripts/run_followups.sh; echo EXIT:$?')
c.close()

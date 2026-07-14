import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import paramiko
from agency_config import ssh_connect

client = paramiko.SSHClient()
ssh_connect(client, timeout=15, banner_timeout=15)

def run(cmd, timeout=15):
    _, out, err = client.exec_command(cmd, timeout=timeout)
    o = out.read().decode('utf-8', errors='replace').strip()
    e = err.read().decode('utf-8', errors='replace').strip()
    if o: print(o)
    if e: print('ERR:', e[:300])
    return o

run('ls /etc/nginx/')
run('ls /etc/nginx/sites-available/ 2>/dev/null || echo "kein sites-available"')
run('ls /etc/nginx/conf.d/ 2>/dev/null || echo "kein conf.d"')
run('nginx -T 2>/dev/null | grep -E "server_name|listen|root" | head -20')
client.close()

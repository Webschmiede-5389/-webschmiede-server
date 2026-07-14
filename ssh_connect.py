import paramiko
from agency_config import load_secrets, ssh_connect

HOST = load_secrets()["SERVER_HOST"]
WEBROOT = '/var/www/snackhouse-mechernich'

client = paramiko.SSHClient()
ssh_connect(client, timeout=15, banner_timeout=15)

sftp = client.open_sftp()
for local, remote_app, webfile in [
    (r'C:\Users\kumex\OneDrive\Desktop\Jarvis\Server\app\static\admin.html',
     '/root/app/static/admin.html', 'admin.html'),
    (r'C:\Users\kumex\OneDrive\Desktop\Jarvis\Server\app\static\order.html',
     '/root/app/static/order.html', 'order.html'),
]:
    sftp.put(local, remote_app)
    print(f'Uploaded {webfile}')
sftp.close()

def run(cmd):
    _, out, err = client.exec_command(cmd, timeout=10)
    o = out.read().decode('utf-8','replace')
    if o.strip(): print(o.strip().encode('ascii','replace').decode())

run(f'cp /root/app/static/admin.html {WEBROOT}/admin.html && cp /root/app/static/order.html {WEBROOT}/order.html && echo OK')
client.close()

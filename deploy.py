"""
Deploy: backend + alle static files → Server
"""
import paramiko, os, sys
from agency_config import load_secrets, ssh_connect

_secrets = load_secrets()
HOST = _secrets["SERVER_HOST"]
USER = _secrets["SERVER_USER"]

LOCAL_BASE  = os.path.join(os.path.dirname(__file__), 'app')
REMOTE_APP  = '/root/app'
WEBROOT     = '/var/www/snackhouse-mechernich'

FILES = [
    (r'backend\main.py',        f'{REMOTE_APP}/backend/main.py'),
    (r'static\order.html',      f'{REMOTE_APP}/static/order.html'),
    (r'static\admin.html',      f'{REMOTE_APP}/static/admin.html'),
    (r'static\index.html',      f'{REMOTE_APP}/static/index.html'),
    (r'static\datenschutz.html',f'{REMOTE_APP}/static/datenschutz.html'),
    (r'static\impressum.html',  f'{REMOTE_APP}/static/impressum.html'),
    (r'static\favicon.png',     f'{REMOTE_APP}/static/favicon.png'),
    (r'static\favicon-192.png', f'{REMOTE_APP}/static/favicon-192.png'),
    (r'static\apple-touch-icon.png', f'{REMOTE_APP}/static/apple-touch-icon.png'),
]

JARVIS_FILES = [
    (r'jarvis\__init__.py',       f'{REMOTE_APP}/jarvis/__init__.py'),
    (r'jarvis\bot.py',            f'{REMOTE_APP}/jarvis/bot.py'),
    (r'jarvis\parser.py',         f'{REMOTE_APP}/jarvis/parser.py'),
    (r'jarvis\permissions.py',    f'{REMOTE_APP}/jarvis/permissions.py'),
    (r'jarvis\menu_catalog.json', f'{REMOTE_APP}/jarvis/menu_catalog.json'),
]

def run(client, cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out.strip(): print(out.strip().encode('ascii','replace').decode())
    if err.strip(): print('ERR:', err.strip()[:400].encode('ascii','replace').decode())
    return out

client = paramiko.SSHClient()
ssh_connect(client, timeout=15, banner_timeout=15)

run(client, f'mkdir -p {REMOTE_APP}/jarvis {REMOTE_APP}/kunden {REMOTE_APP}/uploads/menu')

sftp = client.open_sftp()

LOCAL_ROOT  = os.path.dirname(LOCAL_BASE)
KUNDEN_LOCAL = os.path.join(LOCAL_ROOT, 'kunden')

for local_rel, remote in FILES + JARVIS_FILES:
    local_path = os.path.join(LOCAL_BASE, local_rel)
    if not os.path.exists(local_path):
        print(f'SKIP (not found): {local_path}')
        continue
    print(f'Upload: {local_rel} -> {remote}')
    sftp.put(local_path, remote)

sftp.close()

# Kunden-JSON deployen
print('\nUpload kunden/*.json...')
run(client, f'mkdir -p {REMOTE_APP}/kunden {REMOTE_APP}/uploads/menu')
if os.path.isdir(KUNDEN_LOCAL):
    sftp = client.open_sftp()
    for fname in os.listdir(KUNDEN_LOCAL):
        if fname.endswith('.json'):
            local = os.path.join(KUNDEN_LOCAL, fname)
            remote = f'{REMOTE_APP}/kunden/{fname}'
            print(f'Upload: kunden/{fname}')
            sftp.put(local, remote)
    sftp.close()

# Statische Dateien in Webroot kopieren
print('\nKopiere statische Dateien in Webroot...')
run(client, f'cp {REMOTE_APP}/static/order.html {WEBROOT}/order.html')
run(client, f'cp {REMOTE_APP}/static/admin.html {WEBROOT}/admin.html')
run(client, f'cp {REMOTE_APP}/static/index.html {WEBROOT}/index.html')
run(client, f'cp {REMOTE_APP}/static/datenschutz.html {WEBROOT}/datenschutz.html')
run(client, f'cp {REMOTE_APP}/static/impressum.html {WEBROOT}/impressum.html')
run(client, f'cp {REMOTE_APP}/static/favicon.png {WEBROOT}/favicon.png')
run(client, f'cp {REMOTE_APP}/static/favicon-192.png {WEBROOT}/favicon-192.png')
run(client, f'cp {REMOTE_APP}/static/apple-touch-icon.png {WEBROOT}/apple-touch-icon.png')

# Backend neu starten
print('\nStarte Backend neu...')
run(client, 'systemctl restart snack-api')
import time; time.sleep(3)
run(client, 'systemctl is-active snack-api')

# Prüfen
print('\nVerifikation...')
run(client, f'grep -c "Online/Offline\|online-toggle\|wait-bar\|loadSiteSettings\|view-artikel" {WEBROOT}/admin.html || echo "0"', timeout=10)
run(client, f'grep -c "loadSiteSettings\|offline-banner\|waitPickup\|wait-badge" {WEBROOT}/order.html || echo "0"', timeout=10)
run(client, 'curl -s http://localhost:5001/api/settings | head -c 200', timeout=10)

client.close()
print('\nDeploy fertig!')

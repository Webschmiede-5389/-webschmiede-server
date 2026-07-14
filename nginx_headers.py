import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import paramiko
from agency_config import ssh_connect

client = paramiko.SSHClient()
ssh_connect(client, timeout=15, banner_timeout=15)

def run(cmd, timeout=20):
    _, out, err = client.exec_command(cmd, timeout=timeout)
    o = out.read().decode('utf-8', errors='replace').strip()
    e = err.read().decode('utf-8', errors='replace').strip()
    if o: print(o)
    if e: print('ERR:', e[:500])
    return o

print("=== Aktuelle Config ===")
cfg = run('cat /etc/nginx/sites-available/snack-house')
print(cfg)

if "X-Frame-Options" in cfg:
    print("\nHeaders bereits vorhanden. Kein Änderungsbedarf.")
else:
    print("\n=== Füge Security Headers ein ===")
    # Neue Config schreiben mit Security Headers nach dem listen Block
    new_cfg = cfg.replace(
        'root /var/www/snackhouse-mechernich;',
        """root /var/www/snackhouse-mechernich;

    # ── Security & DSGVO Headers ──────────────────────────
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), interest-cohort=()" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com; style-src 'self' 'unsafe-inline' https://fonts.bunny.net https://cdnjs.cloudflare.com; font-src 'self' https://fonts.bunny.net https://cdnjs.cloudflare.com; img-src 'self' data: https://images.unsplash.com https://files.catbox.moe; connect-src 'self'; frame-ancestors 'none';" always;"""
    )
    
    # Config hochladen
    sftp = client.open_sftp()
    with sftp.open('/etc/nginx/sites-available/snack-house', 'w') as f:
        f.write(new_cfg)
    sftp.close()
    print("Config geschrieben.")
    
    # Testen
    result = run('nginx -t 2>&1')
    if 'successful' in result:
        run('systemctl reload nginx')
        print("Nginx erfolgreich neu geladen!")
    else:
        print("FEHLER beim Nginx-Test!")

print("\n=== Neue Config (erste 50 Zeilen) ===")
run('head -50 /etc/nginx/sites-available/snack-house')
client.close()
print("Fertig!")

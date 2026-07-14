"""Fügt Security-Header in Nginx-Config ein und lädt Nginx neu."""
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

# Aktuelle Config lesen
print("=== Aktuelle Nginx-Config ===")
cfg = run('cat /etc/nginx/sites-available/snackhouse-mechernich')
print(cfg[:3000])
print("...")

# Security Headers Block
SECURITY_HEADERS = """
    # ── Security & DSGVO Headers ──────────────────────────────────────────
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), interest-cohort=()" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com; style-src 'self' 'unsafe-inline' https://fonts.bunny.net https://cdnjs.cloudflare.com; font-src 'self' https://fonts.bunny.net https://cdnjs.cloudflare.com; img-src 'self' data: https://images.unsplash.com https://files.catbox.moe; connect-src 'self'; frame-ancestors 'none';" always;
    more_clear_headers Server;
"""

# Prüfen ob Headers bereits drin sind
if "X-Frame-Options" in cfg:
    print("\nSecurity Headers sind bereits vorhanden. Nginx-Reload...")
    run('nginx -t && systemctl reload nginx')
else:
    print("\nFüge Security Headers ein...")
    # Füge nach dem ersten 'server {' Block ein
    # Einfachster Ansatz: sed-Ersatz nach 'listen 80;' oder 'server_name'
    run(r"""sed -i '/server_name/a\
\
    # Security \& DSGVO Headers\
    add_header X-Frame-Options "DENY" always;\
    add_header X-Content-Type-Options "nosniff" always;\
    add_header Referrer-Policy "no-referrer" always;\
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), interest-cohort=()" always;\
    add_header X-XSS-Protection "1; mode=block" always;\
    add_header Content-Security-Policy "default-src '"'"'self'"'"'; script-src '"'"'self'"'"' '"'"'unsafe-inline'"'"' '"'"'unsafe-eval'"'"' https://cdn.tailwindcss.com; style-src '"'"'self'"'"' '"'"'unsafe-inline'"'"' https://fonts.bunny.net https://cdnjs.cloudflare.com; font-src '"'"'self'"'"' https://fonts.bunny.net https://cdnjs.cloudflare.com; img-src '"'"'self'"'"' data: https://images.unsplash.com https://files.catbox.moe; connect-src '"'"'self'"'"'; frame-ancestors '"'"'none'"'"';" always;' /etc/nginx/sites-available/snackhouse-mechernich""")
    
    out = run('nginx -t 2>&1')
    if 'successful' in out or out == '':
        run('systemctl reload nginx')
        print("Nginx neu geladen.")
    else:
        print("Nginx-Test fehlgeschlagen:", out)

print("\n=== Neue Config (Anfang) ===")
print(run('head -60 /etc/nginx/sites-available/snackhouse-mechernich'))

client.close()
print("Fertig!")

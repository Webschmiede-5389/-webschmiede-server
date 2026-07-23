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
    if e: print('ERR:', e[:300])
    return o

CLEAN_CONFIG = r"""server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    root /var/www/snackhouse-mechernich;
    index index.html;

    # Bestellportal
    location = /bestellen {
        try_files /order.html =404;
    }

    # Admin Dashboard
    location = /admin {
        try_files /admin.html =404;
    }

    # Akquise Lead-Report
    location = /akquise {
        try_files /akquise-report.html =404;
    }

    # Agency Admin & Tools (Snack-Server Webroot)
    location = /angebote {
        try_files /angebote.html =404;
    }
    location = /seminare {
        try_files /seminare.html =404;
    }
    location = /agency {
        try_files /agency.html =404;
    }
    location = /agency-keys {
        try_files /agency-setup.html =404;
    }
    location = /agency-setup {
        try_files /agency-setup.html =404;
    }
    location = /onboarding {
        try_files /onboarding.html =404;
    }

    # Datenschutz & Impressum
    location = /datenschutz {
        try_files /datenschutz.html =404;
    }
    location = /impressum {
        try_files /impressum.html =404;
    }

    # n8n Automation Hub
    location /n8n/ {
        proxy_pass         http://127.0.0.1:5678/n8n/;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
        chunked_transfer_encoding off;
    }

    # Backend API Proxy
    location /api/ {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 30;
    }

    # Hauptseite
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Crawler blockieren
    location = /robots.txt {
        add_header Content-Type text/plain;
        return 200 "User-agent: *\nDisallow: /bestellen\nDisallow: /admin\nDisallow: /agency\nDisallow: /agency-keys\nDisallow: /api/\n";
    }

    # Security & DSGVO Headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), interest-cohort=()" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com; style-src 'self' 'unsafe-inline' https://fonts.bunny.net https://cdnjs.cloudflare.com; font-src 'self' https://fonts.bunny.net https://cdnjs.cloudflare.com; img-src 'self' data: https://images.unsplash.com https://files.catbox.moe; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self';" always;
}
"""

sftp = client.open_sftp()
with sftp.open('/etc/nginx/sites-available/snack-house', 'w') as f:
    f.write(CLEAN_CONFIG)
sftp.close()
print("Nginx-Config aktualisiert.")

result = run('nginx -t 2>&1')
if 'successful' in result:
    run('systemctl reload nginx')
    print("Nginx neu geladen.")
else:
    print("FEHLER:", result)

print("\nRouten-Check:")
run('curl -so /dev/null -w "%{http_code}" http://localhost/datenschutz')
run('curl -so /dev/null -w "%{http_code}" http://localhost/seminare')
run('curl -so /dev/null -w "%{http_code}" http://localhost/agency')

client.close()
print("Fertig!")

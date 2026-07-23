#!/usr/bin/env python3
"""Yassine SSL + Go-Live Env-Grundlagen reparieren."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paramiko
from agency_config import ssh_connect

NGINX = r"""server {
    listen 80;
    listen [::]:80;
    server_name yassine.digitalehandwerkskunst.de;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name yassine.digitalehandwerkskunst.de;

    ssl_certificate     /etc/letsencrypt/live/yassine.digitalehandwerkskunst.de/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yassine.digitalehandwerkskunst.de/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    root /var/www/snackhouse-mechernich;
    index index.html;

    location = /bestellen { try_files /order.html =404; }
    location = /admin { try_files /admin.html =404; }
    location = /onboarding { try_files /onboarding.html =404; }
    location = /datenschutz { try_files /datenschutz.html =404; }
    location = /impressum { try_files /impressum.html =404; }

    location /api/ {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 30;
    }

    location /uploads/ {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
    }

    location / { try_files $uri $uri/ /index.html; }

    location = /robots.txt {
        add_header Content-Type text/plain;
        return 200 "User-agent: *\nDisallow: /admin\nDisallow: /api/\n";
    }

    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer" always;
}
"""

CONF = "/etc/nginx/sites-enabled/kunde-yassine.digitalehandwerkskunst.de"

c = paramiko.SSHClient()
ssh_connect(c)
sftp = c.open_sftp()
with sftp.file("/tmp/kunde-yassine.nginx", "w") as f:
    f.write(NGINX)
sftp.close()

def run(cmd, timeout=60):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode(errors="replace").strip()
    err = e.read().decode(errors="replace").strip()
    if out:
        print(out)
    if err:
        print("ERR:", err[:400])
    return out

# Ensure ssl snippets exist
run("test -f /etc/letsencrypt/options-ssl-nginx.conf || certbot --nginx 2>/dev/null | head -1 || true")
run("ls /etc/letsencrypt/live/yassine.digitalehandwerkskunst.de/")
run(f"cp {CONF} {CONF}.bak.$(date +%Y%m%d%H%M)")
run(f"cp /tmp/kunde-yassine.nginx {CONF}")
run("nginx -t")
run("systemctl reload nginx")

# Env basics: KUNDE_ID, OWNER_PHONE from kunden.json (Festnetz as interim? Better use E.164 from whatsapp)
# Use +4924433088966 from whatsapp allowed - that's likely the shop landline in E.164, not Hassan's mobile
# Set KUNDE_ID only for now; OWNER_PHONE wait for user or use shop phone for owner alerts temporarily
run(
    "grep -q '^KUNDE_ID=' /root/app/backend/.env && "
    "sed -i 's|^KUNDE_ID=.*|KUNDE_ID=SHY001|' /root/app/backend/.env || "
    "echo 'KUNDE_ID=SHY001' >> /root/app/backend/.env"
)
# If OWNER_PHONE empty, set shop contact as interim (better than nothing for test)
run(
    "grep -q '^OWNER_PHONE=$' /root/app/backend/.env || "
    "grep -q '^OWNER_PHONE=$' /root/app/backend/.env; "
    "VAL=$(grep '^OWNER_PHONE=' /root/app/backend/.env | cut -d= -f2-); "
    "if [ -z \"$VAL\" ]; then "
    "  if grep -q '^OWNER_PHONE=' /root/app/backend/.env; then "
    "    sed -i 's|^OWNER_PHONE=.*|OWNER_PHONE=+4924433088966|' /root/app/backend/.env; "
    "  else echo 'OWNER_PHONE=+4924433088966' >> /root/app/backend/.env; fi; "
    "  echo set_owner_interim; "
    "else echo owner_already_set; fi"
)

run("systemctl restart snack-api")
time.sleep(2)
run("systemctl is-active snack-api")

print("\n=== probes ===")
run("curl -s -o /dev/null -w 'https_health:%{http_code}\\n' https://yassine.digitalehandwerkskunst.de/api/health")
run("curl -s -o /dev/null -w 'https_bestellen:%{http_code}\\n' https://yassine.digitalehandwerkskunst.de/bestellen")
run("curl -s -o /dev/null -w 'https_admin:%{http_code}\\n' https://yassine.digitalehandwerkskunst.de/admin")
run("openssl s_client -connect yassine.digitalehandwerkskunst.de:443 -servername yassine.digitalehandwerkskunst.de </dev/null 2>/dev/null | openssl x509 -noout -subject -ext subjectAltName 2>/dev/null | head -10")

c.close()
print("\nDONE")

#!/usr/bin/env python3
"""Yassine-Nginx: Handbuch-Route + aktuelle SSL-Config."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paramiko
from agency_config import ssh_connect

CONF = "/etc/nginx/sites-enabled/kunde-yassine.digitalehandwerkskunst.de"
NGINX = r"""server {
    listen 80;
    listen [::]:80;
    server_name yassine.digitalehandwerkskunst.de;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
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
    location = /uebergabe-handbuch { try_files /uebergabe-handbuch.html =404; }
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

c = paramiko.SSHClient()
ssh_connect(c)
sftp = c.open_sftp()
with sftp.file("/tmp/kunde-yassine.nginx", "w") as f:
    f.write(NGINX)
sftp.close()

def run(cmd):
    _, o, e = c.exec_command(cmd, timeout=30)
    print(o.read().decode(errors="replace").strip())
    err = e.read().decode(errors="replace").strip()
    if err:
        print("ERR:", err[:300])

run(f"cp /tmp/kunde-yassine.nginx {CONF}")
run("nginx -t && systemctl reload nginx")
run("curl -s -o /dev/null -w 'handbuch:%{http_code}\\n' 'https://yassine.digitalehandwerkskunst.de/uebergabe-handbuch?k=SHY001'")
c.close()

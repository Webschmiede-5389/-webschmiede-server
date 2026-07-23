"""Nginx /cal/ mit proxy_redirect fixen."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agency_config import ssh_connect
import paramiko

NGINX_SITE = "/etc/nginx/sites-available/snack-house"
BLOCK = """
    # Cal.com 1:1 booking
    location /cal/ {
        proxy_pass         http://127.0.0.1:3000/;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_set_header   X-Forwarded-Host $host;
        proxy_read_timeout 300;
        proxy_redirect     / /cal/;
        proxy_redirect     http://$host/ /cal/;
        proxy_redirect     http://127.0.0.1:3000/ /cal/;
    }

    location = /cal {
        return 301 /cal/;
    }
"""

c = paramiko.SSHClient()
ssh_connect(c, timeout=25, banner_timeout=25)
sftp = c.open_sftp()
with sftp.open(NGINX_SITE) as f:
    conf = f.read().decode()

import re
conf2 = re.sub(
    r"\n\s*# Cal\.com 1:1 booking.*?location = /cal \{[^}]*\}\n",
    "\n",
    conf,
    flags=re.S,
)
# also remove simple cal block if rewrite above missed
conf2 = re.sub(
    r"\n\s*# Cal\.com 1:1 booking\n\s*location /cal/ \{.*?\n\s*\}\n",
    "\n",
    conf2,
    flags=re.S,
)

if "location /cal/" in conf2 and "proxy_redirect" not in conf2:
    conf2 = re.sub(
        r"\n\s*# Cal\.com 1:1 booking\n\s*location /cal/ \{.*?\n\s*\}\n",
        "\n",
        conf2,
        flags=re.S,
    )

if "location /cal/" not in conf2 or "proxy_redirect" not in conf2:
    # remove any leftover incomplete cal blocks
    conf2 = re.sub(
        r"\n\s*location /cal/ \{.*?\n\s*\}\n",
        "\n",
        conf2,
        flags=re.S,
    )
    conf2 = conf2.replace("    # Backend API Proxy", BLOCK + "\n    # Backend API Proxy")

with sftp.open(NGINX_SITE, "w") as f:
    f.write(conf2)
sftp.close()

_, o, e = c.exec_command("nginx -t && systemctl reload nginx", timeout=30)
print((o.read() + e.read()).decode())
_, o, e = c.exec_command(
    "curl -sI -m 10 http://127.0.0.1/cal/ | head -15; echo '---'; curl -sI -m 10 -L --max-redirs 0 http://127.0.0.1/cal/auth/login | head -15",
    timeout=30,
)
print((o.read() + e.read()).decode())
_, o, e = c.exec_command("grep -A20 'location /cal' /etc/nginx/sites-available/snack-house", timeout=20)
print(o.read().decode())
c.close()

"""Nginx /cal/ prüfen und ggf. nachziehen."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agency_config import ssh_connect
import paramiko

NGINX_SITE = "/etc/nginx/sites-available/snack-house"
NGINX_CAL = r"""
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
        proxy_read_timeout 300;
    }
"""

c = paramiko.SSHClient()
ssh_connect(c, timeout=25, banner_timeout=25)


def run(cmd, timeout=60):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    return o.read().decode("utf-8", "replace"), e.read().decode("utf-8", "replace")


out, _ = run(f"grep -n 'location /cal' {NGINX_SITE} || echo MISSING")
print("cal loc:", out)
if "MISSING" in out:
    conf, _ = run(f"cat {NGINX_SITE}")
    marker = "    # Backend API Proxy"
    if marker in conf:
        conf = conf.replace(marker, NGINX_CAL + "\n" + marker)
    elif "    location /api/ {" in conf:
        conf = conf.replace("    location /api/ {", NGINX_CAL + "\n    location /api/ {")
    else:
        print("NO MARKER")
        c.close()
        sys.exit(1)
    sftp = c.open_sftp()
    with sftp.open(NGINX_SITE, "w") as f:
        f.write(conf)
    sftp.close()
    out, err = run("nginx -t && systemctl reload nginx")
    print(out, err)

for url in ["http://127.0.0.1:3000/", "http://127.0.0.1/cal/", "http://167.233.211.170/cal/"]:
    o, _ = run(f"curl -sI -m 10 {url} | head -8")
    print("===", url)
    print(o.encode("ascii", "replace").decode())

c.close()

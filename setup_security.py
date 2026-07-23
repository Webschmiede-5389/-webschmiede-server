#!/usr/bin/env python3
"""UFW firewall + fail2ban on Webschmiede Hetzner server."""
import paramiko
from agency_config import load_secrets, ssh_connect

NGINX_SITE = '/etc/nginx/sites-available/snack-house'
NGINX_CONF = '/etc/nginx/nginx.conf'

FAIL2BAN_JAIL = """[DEFAULT]
bantime  = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port    = ssh
logpath = %(sshd_log)s
backend = %(sshd_backend)s
"""


def connect():
    c = paramiko.SSHClient()
    ssh_connect(c, timeout=20, banner_timeout=20)
    return c


def run(client, cmd, timeout=120):
    _, out, err = client.exec_command(cmd, timeout=timeout)
    o = out.read().decode('utf-8', errors='replace').strip()
    e = err.read().decode('utf-8', errors='replace').strip()
    if o:
        print(o.encode('ascii', 'replace').decode())
    if e and 'WARNING' not in e.upper() and 'nginx: configuration file' not in e:
        print('ERR:', e[:500].encode('ascii', 'replace').decode())
    return o


def patch_nginx(client):
    py = f'''
from pathlib import Path

zones = """
    limit_req_zone $binary_remote_addr zone=api_order:10m rate=5r/m;
    limit_req_zone $binary_remote_addr zone=api_login:10m rate=10r/m;
"""
locs = """
    location = /api/order {{
        limit_req zone=api_order burst=3 nodelay;
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
    }}

    location = /api/admin/login {{
        limit_req zone=api_login burst=5 nodelay;
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
    }}
"""

conf = Path("{NGINX_CONF}")
text = conf.read_text()
if "zone=api_order" not in text and "http {{" in text:
    text = text.replace("http {{", "http {{" + zones, 1)
    conf.write_text(text)
    print("nginx.conf zones added")

site = Path("{NGINX_SITE}")
st = site.read_text()
if "zone=api_order burst" in st:
    print("site already patched")
else:
    if "location /api/" in st:
        st = st.replace("location /api/", locs + "\\n\\n    location /api/", 1)
    elif "location / {{" in st:
        st = st.replace("location / {{", locs + "\\n\\n    location / {{", 1)
    else:
        raise SystemExit("Could not find nginx insert point")
    site.write_text(st)
    print("site locations added")
'''
    sftp = client.open_sftp()
    with sftp.file('/tmp/patch_nginx_security.py', 'w') as f:
        f.write(py)
    sftp.close()
    run(client, 'python3 /tmp/patch_nginx_security.py')
    run(client, 'nginx -t && systemctl reload nginx')


def main():
    client = connect()

    print('=== UFW ===')
    run(client, 'ufw status verbose | head -20')

    print('\n=== fail2ban ===')
    run(client, 'fail2ban-client status sshd 2>/dev/null || fail2ban-client status')

    print('\n=== nginx rate limits ===')
    run(client, f"sed -i '/limit_req_zone/d' {NGINX_SITE}")
    patch_nginx(client)

    print('\n=== API status ===')
    run(client, 'systemctl is-active snack-api')
    run(client, 'journalctl -u snack-api -n 15 --no-pager')
    run(client, 'curl -s -o /dev/null -w "%{{http_code}}" http://127.0.0.1:8000/api/health')

    client.close()
    print('\nSecurity setup done.')


if __name__ == '__main__':
    main()

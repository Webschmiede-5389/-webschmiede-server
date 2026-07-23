"""Install certbot and enable SSL for digitalehandwerkskunst.de."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect

DOMAIN = "digitalehandwerkskunst.de"
EMAIL = "info@digitalehandwerkskunst.de"

client = paramiko.SSHClient()
ssh_connect(client)

def run(cmd, timeout=180):
    print(f"\n$ {cmd}")
    _, out, err = client.exec_command(cmd, timeout=timeout)
    o = out.read().decode("utf-8", errors="replace").strip()
    e = err.read().decode("utf-8", errors="replace").strip()
    safe = lambda s: s.encode("ascii", "replace").decode()
    if o:
        print(safe(o))
    if e:
        print("ERR:", safe(e[:800]))
    return o

run("which certbot || apt-get install -y -qq certbot python3-certbot-nginx")
run(
    f"certbot --nginx -d {DOMAIN} -d www.{DOMAIN} "
    f"--non-interactive --agree-tos -m {EMAIL} --redirect",
    timeout=180,
)
run("nginx -t && systemctl reload nginx")
run("nginx -T 2>/dev/null | grep -E 'listen 443|ssl_certificate' | head -6")
run(f'curl -sk -o /dev/null -w "https agency-keys: %{{http_code}}\\n" --resolve {DOMAIN}:443:127.0.0.1 https://{DOMAIN}/agency-keys')

client.close()
print("\nFertig.")

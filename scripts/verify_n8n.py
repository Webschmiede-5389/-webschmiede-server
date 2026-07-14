import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import load_secrets, ssh_connect

HOST = load_secrets()["SERVER_HOST"]
c = paramiko.SSHClient()
ssh_connect(c, timeout=20, banner_timeout=20)


def run(cmd, t=45):
    _, o, e = c.exec_command(cmd, timeout=t)
    out = o.read().decode("utf-8", errors="replace").strip()
    err = e.read().decode("utf-8", errors="replace").strip()
    return out, err


out, _ = run('grep -E "location /n8n|location /uploads" /etc/nginx/sites-available/snack-house || echo NO_N8N')
print("NGINX:", out)

out, _ = run("systemctl is-active n8n 2>/dev/null; systemctl is-active snack-api")
print("SERVICES:", out)

out, _ = run("systemctl restart n8n; sleep 12; systemctl is-active n8n", t=60)
print("N8N RESTART:", out)

out, _ = run('curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5678/')
print("N8N LOCAL HTTP:", out)

out, _ = run('curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/n8n/')
print("N8N PROXY HTTP:", out)

out, _ = run("curl -s http://127.0.0.1:8000/api/health")
print("HEALTH:", out)

pw, _ = run("grep N8N_BASIC_AUTH_PASSWORD= /opt/n8n/.env | cut -d= -f2")
cred = os.path.join(os.path.dirname(__file__), "..", "n8n-credentials.local.txt")
with open(cred, "w", encoding="utf-8") as f:
    f.write(f"n8n URL:      http://{HOST}/n8n/\n")
    f.write("n8n User:     webschmiede\n")
    f.write(f"n8n Password: {pw}\n")
print("CREDS WRITTEN")

c.close()

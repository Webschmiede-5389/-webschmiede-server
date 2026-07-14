"""Jarvis Test-Webhook gegen Live-Server."""
import json
import sys
import paramiko
from agency_config import load_secrets, ssh_connect

HOST = load_secrets()["SERVER_HOST"]

def get_secret():
    c = paramiko.SSHClient()
    ssh_connect(c, timeout=15, banner_timeout=15)
    _, o, _ = c.exec_command('grep ^JARVIS_BOT_SECRET= /root/app/backend/.env | cut -d= -f2', timeout=10)
    secret = o.read().decode().strip()
    c.close()
    return secret

def test(text, phone='+4924433088966', client_id=None, agency=False):
    import urllib.request
    secret = get_secret()
    if not secret:
        print('JARVIS_BOT_SECRET fehlt – setup_jarvis_env.py ausführen')
        sys.exit(1)
    body = {'phone': phone, 'text': text}
    if client_id:
        body['client_id'] = client_id
    if agency:
        body['agency'] = True
    req = urllib.request.Request(
        f'http://{HOST}/api/jarvis/test',
        data=json.dumps(body).encode(),
        headers={
            'Content-Type': 'application/json',
            'X-Bot-Secret': secret,
            **({'X-Agency': '1'} if agency else {}),
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode())
    sys.stdout.buffer.write(json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'))
    sys.stdout.buffer.write(b'\n')
    return data

if __name__ == '__main__':
    msg = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else 'Lahmacun-Rolle 7,80 €'
    test(msg)

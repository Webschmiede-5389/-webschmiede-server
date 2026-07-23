#!/usr/bin/env python3
"""Set Telegram webhook on server + optional getUpdates for chat_id."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paramiko
from agency_config import ssh_connect


def main() -> int:
    client = paramiko.SSHClient()
    ssh_connect(client, timeout=15, banner_timeout=15, role="web")
    cmd = r"""
set -e
# Secrets in Backend-Env sicherstellen + Dienst neu laden
python3 - <<'PY'
from pathlib import Path
import os, json, urllib.request

vals = {}
for p in (Path('/root/app/deploy.secrets.local'), Path('/root/app/backend/.env')):
    if not p.exists():
        continue
    for line in p.read_text(errors='replace').splitlines():
        s = line.strip()
        if not s or s.startswith('#') or '=' not in s:
            continue
        k, v = s.split('=', 1)
        vals.setdefault(k.strip(), v.strip().strip('"').strip("'"))

token = (vals.get('TELEGRAM_BOT_TOKEN') or '').strip()
if not token:
    raise SystemExit('NO_TOKEN')

# ensure .env has token for snack-api
env_path = Path('/root/app/backend/.env')
lines = env_path.read_text(errors='replace').splitlines() if env_path.exists() else []
found = False
out = []
for line in lines:
    if line.startswith('TELEGRAM_BOT_TOKEN='):
        out.append(f'TELEGRAM_BOT_TOKEN={token}')
        found = True
    else:
        out.append(line)
if not found:
    out.append(f'TELEGRAM_BOT_TOKEN={token}')
env_path.write_text('\n'.join(out) + '\n', encoding='utf-8')
print('env_synced', True)

hook = 'https://digitalehandwerkskunst.de/api/telegram/webhook'
payload = json.dumps({
    'url': hook,
    'allowed_updates': ['message', 'edited_message'],
    'drop_pending_updates': False,
}).encode()
req = urllib.request.Request(
    f'https://api.telegram.org/bot{token}/setWebhook',
    data=payload,
    headers={'Content-Type': 'application/json'},
    method='POST',
)
with urllib.request.urlopen(req, timeout=20) as r:
    data = json.loads(r.read().decode())
print('setWebhook_ok', data.get('ok'), data.get('description', ''))

# getMe
with urllib.request.urlopen(f'https://api.telegram.org/bot{token}/getMe', timeout=15) as r:
    me = json.loads(r.read().decode())
bot = (me.get('result') or {})
print('bot_username', bot.get('username'))
print('bot_id', bot.get('id'))

# getUpdates for chat ids
with urllib.request.urlopen(f'https://api.telegram.org/bot{token}/getUpdates', timeout=15) as r:
    updates = json.loads(r.read().decode())
ids = []
for u in updates.get('result') or []:
    msg = u.get('message') or u.get('edited_message') or {}
    chat = msg.get('chat') or {}
    cid = chat.get('id')
    if cid is not None and str(cid) not in ids:
        ids.append(str(cid))
print('seen_chat_ids', ','.join(ids) if ids else '(none)')

with urllib.request.urlopen(f'https://api.telegram.org/bot{token}/getWebhookInfo', timeout=15) as r:
    info = json.loads(r.read().decode()).get('result') or {}
print('webhook_url', (info.get('url') or '')[:120])
print('pending', info.get('pending_update_count'))
print('last_error', (info.get('last_error_message') or '')[:160])
PY

systemctl restart snack-api
sleep 2
systemctl is-active snack-api
"""
    _, stdout, stderr = client.exec_command(cmd)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print(err, file=sys.stderr)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

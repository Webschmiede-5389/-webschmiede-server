#!/usr/bin/env python3
"""Verify Telegram owner chat + send test ping (no secrets printed)."""
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
python3 - <<'PY'
from pathlib import Path
import json, urllib.request

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
chat = (vals.get('TELEGRAM_OWNER_CHAT_ID') or vals.get('TELEGRAM_OWNER_CHAT_IDS') or '').strip()
print('token_set', bool(token))
print('chat_set', bool(chat))
print('chat_masked', ('…' + chat[-4:]) if len(chat) > 4 else chat)

# sync chat into .env if only in secrets
env_path = Path('/root/app/backend/.env')
lines = env_path.read_text(errors='replace').splitlines() if env_path.exists() else []
changed = False
out = []
seen = set()
for key in ('TELEGRAM_BOT_TOKEN', 'TELEGRAM_OWNER_CHAT_ID'):
    val = (vals.get(key) or '').strip()
    if not val:
        continue
    found = False
    new_out = []
    source = out if out else lines
    # rebuild once
    pass

# rebuild env keys
keys_wanted = {
    'TELEGRAM_BOT_TOKEN': token,
    'TELEGRAM_OWNER_CHAT_ID': chat.split(',')[0].strip() if chat else '',
}
out = []
seen = set()
for line in lines:
    if '=' in line and not line.strip().startswith('#'):
        k = line.split('=', 1)[0].strip()
        if k in keys_wanted and keys_wanted[k]:
            out.append(f'{k}={keys_wanted[k]}')
            seen.add(k)
            if line != f'{k}={keys_wanted[k]}':
                changed = True
            continue
    out.append(line)
for k, v in keys_wanted.items():
    if v and k not in seen:
        out.append(f'{k}={v}')
        changed = True
if changed:
    env_path.write_text('\n'.join(out) + '\n', encoding='utf-8')
print('env_synced', changed)

if not token or not chat:
    raise SystemExit(0)

cid = chat.split(',')[0].strip()
payload = json.dumps({
    'chat_id': cid,
    'text': 'Nils hier. Telegram Ops ist scharf. Schreib „Status“ oder einen Auftrag.',
    'disable_web_page_preview': True,
}).encode()
req = urllib.request.Request(
    f'https://api.telegram.org/bot{token}/sendMessage',
    data=payload,
    headers={'Content-Type': 'application/json'},
    method='POST',
)
with urllib.request.urlopen(req, timeout=20) as r:
    data = json.loads(r.read().decode())
print('ping_ok', data.get('ok'))
if not data.get('ok'):
    print('ping_error', (data.get('description') or '')[:160])
else:
    print('message_id', (data.get('result') or {}).get('message_id'))
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

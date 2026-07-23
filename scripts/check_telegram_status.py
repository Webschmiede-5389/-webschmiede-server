#!/usr/bin/env python3
"""Check Telegram ops config on server (no secrets printed)."""
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
vals = {}
for p in (Path('/root/app/deploy.secrets.local'), Path('/root/app/backend/.env')):
    if not p.exists():
        continue
    for line in p.read_text(errors='replace').splitlines():
        s = line.strip()
        if not s or s.startswith('#') or '=' not in s:
            continue
        k, v = s.split('=', 1)
        vals[k.strip()] = v.strip().strip('"').strip("'")
token = (vals.get('TELEGRAM_BOT_TOKEN') or '').strip()
chat = (vals.get('TELEGRAM_OWNER_CHAT_ID') or vals.get('TELEGRAM_OWNER_CHAT_IDS') or '').strip()
print('token_set', bool(token))
print('chat_set', bool(chat))
if not token:
    raise SystemExit(0)
import urllib.request, json
url = f'https://api.telegram.org/bot{token}/getWebhookInfo'
with urllib.request.urlopen(url, timeout=15) as r:
    data = json.loads(r.read().decode())
res = data.get('result') or {}
print('webhook_url', (res.get('url') or '')[:100])
print('pending', res.get('pending_update_count'))
err = res.get('last_error_message') or ''
print('last_error', err[:160])
PY
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

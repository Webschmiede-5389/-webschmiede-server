#!/usr/bin/env python3
"""Wire OLLAMA_URL on web-01 → auto-01:11434 and smoke-test chat."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paramiko
from agency_config import load_secrets, ssh_connect


def main() -> int:
    sec = load_secrets()
    auto = (sec.get("AUTO_HOST") or "").strip()
    if not auto:
        print("FAIL: AUTO_HOST fehlt lokal")
        return 1
    ollama_url = f"http://{auto}:11434"
    print("auto_set", True)
    print("ollama_url_host", auto.split(".")[0] + ".…")

    client = paramiko.SSHClient()
    ssh_connect(client, timeout=15, banner_timeout=15, role="web")
    cmd = f"""
python3 - <<'PY'
from pathlib import Path
url = {ollama_url!r}
model = 'llama3.2:1b'
env = Path('/root/app/backend/.env')
lines = env.read_text(errors='replace').splitlines() if env.exists() else []
keys = {{
    'OLLAMA_URL': url,
    'OLLAMA_MODEL': model,
    'LLM_PROVIDER': 'auto',
}}
out, seen = [], set()
for line in lines:
    if '=' in line and not line.strip().startswith('#'):
        k = line.split('=', 1)[0].strip()
        if k in keys:
            out.append(f'{{k}}={{keys[k]}}')
            seen.add(k)
            continue
    out.append(line)
for k, v in keys.items():
    if k not in seen:
        out.append(f'{{k}}={{v}}')
env.write_text('\\n'.join(out) + '\\n', encoding='utf-8')
print('env_written', True)

import json, urllib.request
# tags
with urllib.request.urlopen(url + '/api/tags', timeout=10) as r:
    tags = json.loads(r.read().decode())
names = [m.get('name') for m in tags.get('models') or []]
print('models', ','.join(names[:6]))

payload = json.dumps({{
    'model': model,
    'stream': False,
    'messages': [
        {{'role': 'system', 'content': 'Du bist Nils. Antworte auf Deutsch in einem kurzen Satz.'}},
        {{'role': 'user', 'content': 'Sag nur: Nils bereit über Ollama.'}},
    ],
    'options': {{'num_predict': 40, 'temperature': 0.3}},
}}).encode()
req = urllib.request.Request(url + '/api/chat', data=payload, headers={{'Content-Type': 'application/json'}})
with urllib.request.urlopen(req, timeout=90) as r:
    data = json.loads(r.read().decode())
text = ((data.get('message') or {{}}).get('content') or '').strip()
print('chat_ok', bool(text))
print('chat_preview', text[:120].replace('\\n', ' '))
PY
systemctl restart snack-api
sleep 2
systemctl is-active snack-api
"""
    _, stdout, stderr = client.exec_command(cmd)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace")
    if err.strip():
        print(err[:400], file=sys.stderr)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

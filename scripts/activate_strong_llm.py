#!/usr/bin/env python3
"""Wait for Ollama pull, switch OLLAMA_MODEL on web, smoke test."""
from __future__ import annotations
import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import paramiko
from agency_config import load_secrets, ssh_connect

MODEL = "qwen2.5:14b"


def main() -> int:
    # poll auto for model
    for i in range(60):
        c = paramiko.SSHClient()
        ssh_connect(c, timeout=20, banner_timeout=20, role="auto")
        _, o, _ = c.exec_command(
            "curl -sf http://127.0.0.1:11434/api/tags | python3 -c "
            "\"import sys,json; d=json.load(sys.stdin); print(','.join(m.get('name','') for m in d.get('models') or []))\" ; "
            "tail -n 2 /tmp/ollama_pull_qwen14.log 2>/dev/null | tr '\\r' '\\n' | tail -n 2"
        )
        out = o.read().decode(errors="replace")
        c.close()
        print(f"[{i}] {out[:200].replace(chr(10),' | ')}")
        if MODEL in out:
            break
        time.sleep(30)
    else:
        print("TIMEOUT waiting for model – falling back check")
        # try 7b
        return pull_fallback()

    return activate(MODEL)


def pull_fallback() -> int:
    print("Trying qwen2.5:7b as fallback…")
    c = paramiko.SSHClient()
    ssh_connect(c, timeout=20, banner_timeout=20, role="auto")
    c.exec_command("docker exec voice-demo-ollama-1 ollama pull qwen2.5:7b > /tmp/ollama_pull_qwen7.log 2>&1 &")
    c.close()
    for i in range(40):
        time.sleep(20)
        c = paramiko.SSHClient()
        ssh_connect(c, timeout=20, banner_timeout=20, role="auto")
        _, o, _ = c.exec_command(
            "curl -sf http://127.0.0.1:11434/api/tags | python3 -c "
            "\"import sys,json; d=json.load(sys.stdin); print([m.get('name') for m in d.get('models') or []])\""
        )
        out = o.read().decode(errors="replace")
        c.close()
        print(f"fb[{i}] {out[:180]}")
        if "qwen2.5:7b" in out:
            return activate("qwen2.5:7b")
    print("FAIL no model")
    return 1


def activate(model: str) -> int:
    sec = load_secrets()
    auto = sec.get("AUTO_HOST", "").strip()
    url = f"http://{auto}:11434"
    c = paramiko.SSHClient()
    ssh_connect(c, timeout=20, banner_timeout=20, role="web")
    cmd = f"""
python3 - <<'PY'
from pathlib import Path
model = {model!r}
url = {url!r}
env = Path('/root/app/backend/.env')
lines = env.read_text(errors='replace').splitlines() if env.exists() else []
keys = {{'OLLAMA_URL': url, 'OLLAMA_MODEL': model, 'LLM_PROVIDER': 'auto'}}
out, seen = [], set()
for line in lines:
    if '=' in line and not line.strip().startswith('#'):
        k = line.split('=',1)[0].strip()
        if k in keys:
            out.append(f'{{k}}={{keys[k]}}'); seen.add(k); continue
    out.append(line)
for k,v in keys.items():
    if k not in seen:
        out.append(f'{{k}}={{v}}')
env.write_text('\\n'.join(out)+'\\n', encoding='utf-8')
print('model_set', model)
import json, urllib.request
payload = json.dumps({{
  'model': model, 'stream': False,
  'messages': [
    {{'role':'system','content':'Du bist Nils. Antworte auf Deutsch in einem Satz.'}},
    {{'role':'user','content':'Sag: Agency-Hirn scharf mit Qwen.'}}
  ],
  'options': {{'num_predict': 60, 'temperature': 0.3}}
}}).encode()
req = urllib.request.Request(url+'/api/chat', data=payload, headers={{'Content-Type':'application/json'}})
with urllib.request.urlopen(req, timeout=180) as r:
    data = json.loads(r.read().decode())
print('chat', ((data.get('message') or {{}}).get('content') or '')[:160])
PY
systemctl restart snack-api
sleep 2
systemctl is-active snack-api
"""
    _, o, e = c.exec_command(cmd)
    print(o.read().decode(errors="replace"))
    err = e.read().decode(errors="replace")
    if err.strip():
        print(err[:400], file=sys.stderr)
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

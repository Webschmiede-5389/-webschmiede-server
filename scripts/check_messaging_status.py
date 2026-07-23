#!/usr/bin/env python3
"""Server-Check: WhatsApp/Messaging Secrets + Health (keine Secrets ausgeben)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paramiko
from agency_config import ssh_connect

REMOTE = r'''
python3 <<'PY'
from pathlib import Path
import re, json, urllib.request
keys = [
  "WHATSAPP_ACCESS_TOKEN","WHATSAPP_PHONE_NUMBER_ID","WHATSAPP_VERIFY_TOKEN",
  "WHATSAPP_DISPLAY_PHONE","WHATSAPP_BUSINESS_ACCOUNT_ID",
  "META_APP_ID","META_APP_SECRET","META_EMBEDDED_CONFIG_ID",
  "SMS_API_KEY","SMS_ENABLED","SMS_SENDER",
  "OWNER_PHONE","AGENCY_OWNER_EMAIL",
]
found = {}
for p in [Path("/root/app/backend/.env"), Path("/root/app/deploy.secrets.local")]:
  if not p.exists():
    continue
  t = p.read_text(errors="replace")
  for k in keys:
    m = re.search(rf"^{k}=(.*)$", t, re.M)
    if m and m.group(1).strip() and k not in found:
      v = m.group(1).strip().strip('"').strip("'")
      found[k] = {"set": True, "len": len(v), "src": p.name}
out = {"secrets": {}}
for k in keys:
  out["secrets"][k] = found.get(k) or {"set": False}

# health
try:
  with urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=8) as r:
    out["health"] = json.loads(r.read().decode())
except Exception as e:
  out["health"] = {"ok": False, "error": str(e)}

# messaging status local import if possible
try:
  import os, sys
  sys.path.insert(0, "/root/app/backend")
  # load env lightly
  envp = Path("/root/app/backend/.env")
  if envp.exists():
    for line in envp.read_text().splitlines():
      if "=" in line and not line.strip().startswith("#"):
        k,v = line.split("=",1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
  from messaging import status
  st = status()
  # strip any tokens if present
  wa = st.get("whatsapp") or {}
  out["messaging"] = {
    "ok": st.get("ok"),
    "whatsapp": {
      "configured": wa.get("configured"),
      "enabled": wa.get("enabled"),
      "verify_token_set": wa.get("verify_token_set"),
      "phone_number_id_set": bool(wa.get("phone_number_id")),
      "display_phone": wa.get("display_phone") or "",
      "webhook_path": wa.get("webhook_path"),
    },
    "sms": {
      "configured": (st.get("sms") or {}).get("configured"),
      "enabled": (st.get("sms") or {}).get("enabled"),
    },
    "tenants": (st.get("whatsapp_tenants") or {}).get("tenant_count"),
  }
except Exception as e:
  out["messaging"] = {"error": str(e)}

# webhook verify probe (GET should challenge if token known)
verify = None
for p in [Path("/root/app/backend/.env"), Path("/root/app/deploy.secrets.local")]:
  if not p.exists(): continue
  m = re.search(r"^WHATSAPP_VERIFY_TOKEN=(.*)$", p.read_text(), re.M)
  if m and m.group(1).strip():
    verify = m.group(1).strip().strip('"').strip("'")
    break
if verify:
  try:
    url = f"http://127.0.0.1:8000/api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token={verify}&hub.challenge=ws_probe_ok"
    with urllib.request.urlopen(url, timeout=8) as r:
      body = r.read().decode()
      out["webhook_verify"] = {"ok": body.strip() == "ws_probe_ok", "body": body[:80]}
  except Exception as e:
    out["webhook_verify"] = {"ok": False, "error": str(e)}
else:
  out["webhook_verify"] = {"ok": False, "error": "no verify token"}

print(json.dumps(out, ensure_ascii=False, indent=2))
PY
'''


def main() -> int:
    c = paramiko.SSHClient()
    ssh_connect(c, timeout=30, banner_timeout=30, role="web")
    _, o, e = c.exec_command(REMOTE, timeout=60)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    c.close()
    print(out)
    if err.strip():
        print("STDERR", err[:800])
    path = ROOT / "docs" / "agency" / "messaging-status-live.json"
    # extract json
    start = out.find("{")
    if start >= 0:
        path.write_text(out[start:], encoding="utf-8")
        print("Wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

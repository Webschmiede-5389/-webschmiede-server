#!/usr/bin/env python3
"""Fact-check DSGVO-relevante Server-Flags (keine Secret-Werte ausgeben)."""
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
import re, json
env = Path("/root/app/backend/.env")
t = env.read_text() if env.exists() else ""
def get(k):
  m = re.search(rf"^{k}=(.*)$", t, re.M)
  if not m:
    return None
  return m.group(1).strip().strip('"').strip("'")
keys_boolish = ["SMS_ENABLED", "GHL_ENABLED"]
keys_set = ["STRIPE_SECRET_KEY", "RETELL_API_KEY", "VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY",
            "WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "SMS_API_KEY",
            "DOCUSEAL_URL", "CALCOM_URL", "PUBLIC_BASE_URL"]
out = {}
for k in keys_boolish:
  v = get(k)
  out[k] = {"raw": v, "truthy": (v or "").lower() in ("1","true","yes")}
for k in keys_set:
  v = get(k)
  if v is None:
    out[k] = {"set": False}
  elif k.endswith("_URL") or k == "PUBLIC_BASE_URL" or k == "CALCOM_URL" or k == "DOCUSEAL_URL":
    out[k] = {"set": True, "value": v[:120]}
  else:
    out[k] = {"set": bool(v), "len": len(v)}
# logrotate
lr = Path("/etc/logrotate.d/nginx")
out["logrotate_nginx"] = {"exists": lr.exists(), "preview": lr.read_text()[:500] if lr.exists() else ""}
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
        print("STDERR", err[:500])
    path = ROOT / "docs" / "agency" / "dsgvo-factcheck-live.json"
    start = out.find("{")
    if start >= 0:
        path.write_text(out[start:], encoding="utf-8")
        print("Wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""SHY001 Go-Live Ist-Zustand (keine Secrets ausgeben)."""
import json
import sys

import paramiko

sys.path.insert(0, ".")
from agency_config import ssh_connect

CHECKS = r'''
import json, os, urllib.request
from pathlib import Path

env = {}
p = Path("/root/app/backend/.env")
if p.is_file():
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line=line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k,v=line.split("=",1)
        env[k.strip()]=v.strip().strip('"').strip("'")

def present(key):
    v = env.get(key,"")
    return bool(v) and v not in ("dein-seven-io-api-key","+491751234567","") and not v.startswith("dein-")

kunden = Path("/root/app/kunden/SHY001_snackhouse.json")
k = json.loads(kunden.read_text(encoding="utf-8")) if kunden.is_file() else {}

def probe(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"GoLive/1"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return {"ok": 200<=r.status<400, "status": r.status}
    except Exception as e:
        return {"ok": False, "error": str(e)[:80]}

out = {
  "env": {
    "KUNDE_ID": env.get("KUNDE_ID",""),
    "SMS_ENABLED": env.get("SMS_ENABLED",""),
    "SMS_API_KEY": present("SMS_API_KEY"),
    "SMS_SENDER": env.get("SMS_SENDER",""),
    "OWNER_PHONE": present("OWNER_PHONE"),
    "OWNER_PHONE_hint": (env.get("OWNER_PHONE","")[:6]+"…") if present("OWNER_PHONE") else "",
    "GOOGLE_REVIEW_URL": present("GOOGLE_REVIEW_URL"),
    "GHL_ENABLED": env.get("GHL_ENABLED",""),
    "SHOP_NAME": env.get("SHOP_NAME",""),
  },
  "kunde": {
    "status": k.get("status"),
    "sms": k.get("sms") or {},
    "whatsapp_enabled": (k.get("whatsapp") or {}).get("enabled"),
    "whatsapp_phones": len((k.get("whatsapp") or {}).get("allowed_phones") or []),
    "voice_enabled": (k.get("voice") or {}).get("enabled"),
    "knowledge_pack": (k.get("knowledge") or {}).get("pack"),
    "offene_punkte": k.get("offene_punkte") or [],
    "urls": {
      "bestellen": (k.get("urls") or {}).get("test_bestellen"),
      "admin": (k.get("urls") or {}).get("test_admin"),
      "onboarding": (k.get("urls") or {}).get("onboarding_url"),
    },
  },
  "probes": {
    "bestellen": probe((k.get("urls") or {}).get("test_bestellen") or ""),
    "admin": probe((k.get("urls") or {}).get("test_admin") or ""),
    "api_health": probe("https://yassine.digitalehandwerkskunst.de/api/health"),
    "api_promo": probe("https://yassine.digitalehandwerkskunst.de/api/promo/active"),
  },
}
# recent orders count
import sqlite3
dbp = Path("/root/app/backend/orders.db")
if dbp.is_file():
    db = sqlite3.connect(str(dbp))
    out["orders_total"] = db.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    out["orders_today"] = db.execute("SELECT COUNT(*) FROM orders WHERE date(created_at)=date('now')").fetchone()[0]
    out["sms_log_7d"] = db.execute("SELECT COUNT(*) FROM message_log WHERE channel='sms' AND created_at>=datetime('now','-7 days')").fetchone()[0]
    row = db.execute("SELECT order_number, status, created_at FROM orders ORDER BY id DESC LIMIT 1").fetchone()
    out["last_order"] = {"nr": row[0], "status": row[1], "at": row[2]} if row else None
print(json.dumps(out, ensure_ascii=False, indent=2))
'''

client = paramiko.SSHClient()
ssh_connect(client)
sftp = client.open_sftp()
with sftp.file("/tmp/shy001_golive_check.py", "w") as f:
    f.write(CHECKS)
sftp.close()
_, out, err = client.exec_command("/root/app/venv/bin/python3 /tmp/shy001_golive_check.py", timeout=40)
print(out.read().decode())
e = err.read().decode()
if e.strip():
    print("ERR:", e[:400])
client.close()

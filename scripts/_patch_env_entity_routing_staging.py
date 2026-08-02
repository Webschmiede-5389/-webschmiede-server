# -*- coding: utf-8 -*-
"""Remote helper: patch .env for entity-routing staging canary."""
from pathlib import Path

STAGING_DB = "/root/app/data/nils-crm-staging-entity-20260802.db"
CODE_VERSION = "2026-08-02-entity-routing-staging-1"
LIVE_CAPS = "crm.offer_read,crm.customer_read,crm.prospect_create"

env = Path("/root/app/backend/.env")
text = env.read_text(encoding="utf-8") if env.exists() else ""
lines = text.splitlines()
kv = {}
order = []
for line in lines:
    if not line.strip() or line.strip().startswith("#") or "=" not in line:
        order.append(("raw", line))
        continue
    k, _, v = line.partition("=")
    kv[k.strip()] = v
    order.append(("kv", k.strip()))

owner = (
    kv.get("TELEGRAM_OWNER_CHAT_ID") or kv.get("TELEGRAM_OWNER_CHAT_IDS") or ""
).split(",")[0].strip()
assert owner, "TELEGRAM_OWNER_CHAT_ID missing — abort staging canary"

updates = {
    "NILS_CONTROL_PLANE": "0",
    "NILS_CONTROL_PLANE_CANARY": "1",
    "NILS_CONTROL_PLANE_STAGING": "1",
    "NILS_CONTROL_PLANE_ALLOWLIST": owner,
    "NILS_CANARY_TELEGRAM_USER_IDS": owner,
    "NILS_CAP_CRM_READ": "1",
    "NILS_CAP_CRM_PROSPECT_CREATE": "1",
    "NILS_CAP_CRM_OFFER_PDF": "0",
    "NILS_CAP_EMAIL_SEND": "0",
    "NILS_CAP_N8N": "0",
    "NILS_CAP_CALENDAR_WRITE": "0",
    "NILS_CAP_DRIVE_WRITE": "0",
    "NILS_WRITE_ENABLED": "false",
    "NILS_JOB_NOTIFY": "1",
    "NILS_CRM_BACKEND": "sqlite",
    "NILS_CRM_DB": STAGING_DB,
    "NILS_CRM_ROOT": "/root/app/crm-read",
    "NILS_CRM_TENANT_ID": "1",
    "NILS_WORKER_LIVE_CAPABILITIES": LIVE_CAPS,
    "NILS_RUNTIME_CODE_VERSION": CODE_VERSION,
    "NILS_CRM_DATABASE_URL": "",
}
for k, v in updates.items():
    kv[k] = v

out_lines = []
seen = set()
for kind, val in order:
    if kind == "raw":
        out_lines.append(val)
        continue
    k = val
    if k in seen:
        continue
    seen.add(k)
    out_lines.append(f"{k}={kv[k]}")
for k, v in kv.items():
    if k not in seen:
        out_lines.append(f"{k}={v}")
env.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
print("STAGING_ENV_OK owner_tail=..." + owner[-4:])
print("CRM_BACKEND", kv.get("NILS_CRM_BACKEND"))
print("CRM_DB", kv.get("NILS_CRM_DB"))
print("CANARY", kv.get("NILS_CONTROL_PLANE_CANARY"))
print("EMAIL", kv.get("NILS_CAP_EMAIL_SEND"), "N8N", kv.get("NILS_CAP_N8N"))
assert (kv.get("NILS_WRITE_ENABLED") or "").lower() in ("0", "false", "")
assert kv.get("NILS_CRM_BACKEND") == "sqlite"
assert kv.get("NILS_CAP_EMAIL_SEND") == "0"
assert kv.get("NILS_CAP_N8N") == "0"

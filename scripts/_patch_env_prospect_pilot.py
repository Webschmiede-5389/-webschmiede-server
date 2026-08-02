# -*- coding: utf-8 -*-
"""Enable ONLY crm.prospect_create for owner limited pilot."""
from pathlib import Path
import sys

release_id = sys.argv[1] if len(sys.argv) > 1 else ""
commit = sys.argv[2] if len(sys.argv) > 2 else ""
enable = (sys.argv[3] if len(sys.argv) > 3 else "1").strip()

p = Path("/root/app/backend/.env")
lines = p.read_text(encoding="utf-8").splitlines()
kv = {}
order = []
for line in lines:
    if not line.strip() or line.strip().startswith("#") or "=" not in line:
        order.append(("raw", line))
        continue
    k, _, v = line.partition("=")
    kv[k.strip()] = v
    order.append(("kv", k.strip()))

owner = (kv.get("TELEGRAM_OWNER_CHAT_ID") or "").split(",")[0].strip()
assert owner, "TELEGRAM_OWNER_CHAT_ID missing"

# Keep canary allowlist — no other users
kv["NILS_CONTROL_PLANE"] = "0"
kv["NILS_CONTROL_PLANE_CANARY"] = "1"
kv["NILS_CONTROL_PLANE_ALLOWLIST"] = owner
kv["NILS_CANARY_TELEGRAM_USER_IDS"] = owner

kv["NILS_CAP_CRM_PROSPECT_CREATE"] = "1" if enable in ("1", "true", "on") else "0"
kv["NILS_CAP_EMAIL_SEND"] = "0"
kv["NILS_CAP_N8N"] = "0"
kv["NILS_CAP_CRM_CUSTOMER_WRITE"] = "0"
kv["NILS_WRITE_ENABLED"] = "0"
kv["NILS_PROSPECT_PILOT_MAX"] = "5"
kv["NILS_PROSPECT_CONFIRM_TTL_SEC"] = "600"
kv["NILS_PROSPECT_PILOT_STATE"] = "/root/app/data/nils-prospect-pilot-state.json"
kv["NILS_PROSPECT_PILOT_AUDIT_DIR"] = "/root/app/data/nils-prospect-pilot-audit"
if release_id:
    kv["NILS_RELEASE_ID"] = release_id
if commit:
    kv["NILS_GIT_COMMIT"] = commit

# Force postgres production CRM
assert (kv.get("NILS_CRM_BACKEND") or "").strip().lower() == "postgres", kv.get(
    "NILS_CRM_BACKEND"
)
assert (kv.get("NILS_CRM_DATABASE_URL") or "").strip(), "missing CRM URL"
assert (kv.get("NILS_CRM_TENANT_ID") or "").strip() == "1", "tenant must be 1 for pilot"

out, seen = [], set()
for kind, val in order:
    if kind == "raw":
        out.append(val)
        continue
    if val in seen:
        continue
    seen.add(val)
    out.append(f"{val}={kv[val]}")
for k, v in kv.items():
    if k not in seen:
        out.append(f"{k}={v}")
p.write_text("\n".join(out) + "\n", encoding="utf-8")
print("PILOT_ENV_OK enable=", kv["NILS_CAP_CRM_PROSPECT_CREATE"], "owner_tail=", owner[-4:])
print("BACKEND", kv.get("NILS_CRM_BACKEND"), "TENANT", kv.get("NILS_CRM_TENANT_ID"))

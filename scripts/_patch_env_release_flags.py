# -*- coding: utf-8 -*-
"""Set Owner-canary flags without enabling production prospect writes."""
from pathlib import Path
import sys

code_version = sys.argv[1] if len(sys.argv) > 1 else ""
release_id = sys.argv[2] if len(sys.argv) > 2 else ""
commit = sys.argv[3] if len(sys.argv) > 3 else ""

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
kv["NILS_CONTROL_PLANE"] = "0"
kv["NILS_CONTROL_PLANE_CANARY"] = "1"
kv["NILS_CONTROL_PLANE_ALLOWLIST"] = owner
kv["NILS_CANARY_TELEGRAM_USER_IDS"] = owner
kv["NILS_CAP_CRM_PROSPECT_CREATE"] = "0"
kv["NILS_CAP_EMAIL_SEND"] = "0"
kv["NILS_CAP_N8N"] = "0"
if code_version:
    kv["NILS_RUNTIME_CODE_VERSION"] = code_version
if release_id:
    kv["NILS_RELEASE_ID"] = release_id
if commit:
    kv["NILS_GIT_COMMIT"] = commit

backend = (kv.get("NILS_CRM_BACKEND") or "").strip().lower()
url = (kv.get("NILS_CRM_DATABASE_URL") or "").strip()
assert backend == "postgres" or url, "production CRM read endpoint missing after patch"

out = []
seen = set()
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
print("ENV_RELEASE_FLAGS_OK", release_id, commit[:12] if commit else "")
print("BACKEND", kv.get("NILS_CRM_BACKEND"), "PROSPECT", kv.get("NILS_CAP_CRM_PROSPECT_CREATE"))

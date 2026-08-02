# -*- coding: utf-8 -*-
"""Immutable file-release deploy for Nils entity-routing (snack-api path).

Creates /root/app/releases/nils-entity-routing-<commit>/ with digests,
atomically switches nils_job_runtime via symlink, clears pycache, restarts.
Does NOT enable production prospect writes.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import paramiko

SERVER = Path(__file__).resolve().parents[1]
BACKEND = SERVER / "app" / "backend"
sys.path.insert(0, str(SERVER))
from agency_config import ssh_connect  # noqa: E402

MODULE_FILES = [
    "turn_routing.py",
    "promise_guard.py",
    "pipeline.py",
    "control_plane.py",
    "crm_prospect_exec.py",
    "crm_prospect_service.py",
    "turn_context.py",
    "store.py",
    "capability_preflight.py",
    "crm_offer_service.py",
    "crm_offer_exec.py",
    "crm_language.py",
    "model.py",
    "__init__.py",
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(client, cmd: str, timeout: int = 180) -> str:
    print("+", cmd[:220])
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = (stdout.read() + stderr.read()).decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[:5000].encode("ascii", "replace").decode("ascii"))
    if code != 0:
        raise RuntimeError(f"exit {code}: {cmd[:140]}")
    return out


def main() -> int:
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=str(SERVER), text=True
    ).strip()
    short = commit[:12]
    release_id = f"nils-entity-routing-{short}"
    code_version = f"2026-08-02-{short}"
    local_nr = BACKEND / "nils_job_runtime"
    digests = {n: sha256_file(local_nr / n) for n in MODULE_FILES if (local_nr / n).is_file()}
    meta = {
        "release_id": release_id,
        "commit": commit,
        "code_version": code_version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "digests": digests,
        "staging_db": f"/root/app/data/nils-crm-staging-entity-{short}.db",
    }
    meta_path = SERVER / "scripts" / f"_release_meta_{short}.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    remote_release = f"/root/app/releases/{release_id}"
    remote_runtime = f"{remote_release}/nils_job_runtime"
    link = "/root/app/backend/nils_job_runtime"

    client = paramiko.SSHClient()
    ssh_connect(client, role="web")
    sftp = client.open_sftp()
    try:
        run(client, f"mkdir -p {remote_runtime} /root/app/releases /root/app/data /root/app/scripts")
        for name in MODULE_FILES:
            lp = local_nr / name
            if lp.is_file():
                print(f"PUT {name}")
                sftp.put(str(lp), f"{remote_runtime}/{name}")
        # full package copy for imports of sibling modules
        for lp in local_nr.glob("*.py"):
            if lp.name not in digests:
                digests[lp.name] = sha256_file(lp)
            sftp.put(str(lp), f"{remote_runtime}/{lp.name}")
        if (local_nr / "ggg_design_rules.json").is_file():
            sftp.put(
                str(local_nr / "ggg_design_rules.json"),
                f"{remote_runtime}/ggg_design_rules.json",
            )
        meta["digests"] = digests
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        sftp.put(str(meta_path), f"{remote_release}/digests.json")
        for fname in (
            "canary_nils_entity_routing_staging.py",
            "rollback_nils_entity_routing_staging.py",
            "_run_remote_entity_routing_final_canary.py",
        ):
            lp = SERVER / "scripts" / fname
            if lp.is_file():
                sftp.put(str(lp), f"/root/app/scripts/{fname}")

        # Atomic switch: backup current dir/symlink, point to release
        run(
            client,
            f"""
set -e
if [ -L {link} ]; then
  rm -f {link}
elif [ -d {link} ]; then
  mv {link} {link}.pre-{short}
fi
ln -sfn {remote_runtime} {link}
# verify digests
python3 - <<'PY'
import hashlib, json
from pathlib import Path
meta=json.loads(Path('{remote_release}/digests.json').read_text())
root=Path('{remote_runtime}')
bad=[]
for name, expect in meta['digests'].items():
    p=root/name
    if not p.is_file():
        bad.append(('missing', name)); continue
    h=hashlib.sha256(p.read_bytes()).hexdigest()
    if h!=expect:
        bad.append(('mismatch', name, h, expect))
if bad:
    raise SystemExit('DIGEST_FAIL '+str(bad[:5]))
print('DIGEST_OK', len(meta['digests']), meta['commit'][:12])
PY
find {link} -name '__pycache__' -type d -exec rm -rf {{}} + 2>/dev/null || true
find {link} -name '*.pyc' -delete 2>/dev/null || true
""",
        )

        # Safe env: canary allowlist, no prospect prod write, keep postgres read
        run(
            client,
            f"""
/root/app/venv/bin/python - <<'PY'
from pathlib import Path
p=Path('/root/app/backend/.env')
lines=p.read_text(encoding='utf-8').splitlines()
kv={{}}; order=[]
for line in lines:
    if not line.strip() or line.strip().startswith('#') or '=' not in line:
        order.append(('raw', line)); continue
    k,_,v=line.partition('=')
    kv[k.strip()]=v; order.append(('kv', k.strip()))
owner=(kv.get('TELEGRAM_OWNER_CHAT_ID') or '').split(',')[0].strip()
kv['NILS_CONTROL_PLANE']='0'
kv['NILS_CONTROL_PLANE_CANARY']='1'
kv['NILS_CONTROL_PLANE_ALLOWLIST']=owner
kv['NILS_CANARY_TELEGRAM_USER_IDS']=owner
kv['NILS_CAP_CRM_PROSPECT_CREATE']='0'
kv['NILS_CAP_EMAIL_SEND']='0'
kv['NILS_CAP_N8N']='0'
kv['NILS_RUNTIME_CODE_VERSION']='{code_version}'
kv['NILS_RELEASE_ID']='{release_id}'
kv['NILS_GIT_COMMIT']='{commit}'
# ensure production CRM read remains
assert (kv.get('NILS_CRM_BACKEND') or '') == 'postgres' or (kv.get('NILS_CRM_DATABASE_URL') or '').strip()
out=[]; seen=set()
for kind,val in order:
    if kind=='raw': out.append(val); continue
    if val in seen: continue
    seen.add(val); out.append(f'{{val}}={{kv[val]}}')
for k,v in kv.items():
    if k not in seen: out.append(f'{{k}}={{v}}')
p.write_text('\\n'.join(out)+'\\n', encoding='utf-8')
print('ENV_RELEASE_FLAGS_OK', '{release_id}')
PY
systemctl restart snack-api nils-job-worker
sleep 2
systemctl is-active snack-api nils-job-worker
readlink -f /root/app/backend/nils_job_runtime
cd /root/app/backend && /root/app/venv/bin/python - <<'PY'
import os
from pathlib import Path
for line in Path('.env').read_text().splitlines():
    if not line or line.startswith('#') or '=' not in line: continue
    k,_,v=line.partition('='); os.environ[k.strip()]=v
from nils_job_runtime import pipeline, turn_routing as tr
assert pipeline.map_capability('Lege Max Mustermann als Ansprechpartner an.')[0]=='crm.prospect_create'
assert pipeline.extract_contact_from_text('Lege Max Mustermann als Ansprechpartner an.')=='Max Mustermann'
assert pipeline.extract_company_from_text('Lege Max Mustermann als Ansprechpartner an.')==''
assert pipeline.map_capability('Lege Hassan Yassine als potentiellen Kunden an.')[0]=='crm.prospect_create'
print('SMOKE_RELEASE_OK', os.environ.get('NILS_RELEASE_ID'), os.environ.get('NILS_GIT_COMMIT','')[:12])
PY
""",
        )
    finally:
        sftp.close()
        client.close()

    print("RELEASE_DEPLOY_OK", release_id, commit)
    print("STAGING_DB_FOR_CANARY", meta["staging_db"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

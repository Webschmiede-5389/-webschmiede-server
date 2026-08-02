# -*- coding: utf-8 -*-
"""Deploy Entity-Routing Fix in isolated STAGING canary mode (web-01)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import paramiko

SERVER = Path(__file__).resolve().parents[1]
BACKEND = SERVER / "app" / "backend"

sys.path.insert(0, str(SERVER))
from agency_config import ssh_connect  # noqa: E402

REMOTE_BACKEND = "/root/app/backend"
REMOTE_SCRIPTS = "/root/app/scripts"
REMOTE_DATA = "/root/app/data"
CODE_VERSION = "2026-08-02-entity-routing-staging-1"
STAGING_DB = f"{REMOTE_DATA}/nils-crm-staging-entity-20260802.db"
BACKUP_ROOT = f"/root/app/backups/nils-entity-routing-{CODE_VERSION}"
LIVE_CAPS = "crm.offer_read,crm.customer_read,crm.prospect_create"

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
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def sftp_put(sftp, local: Path, remote: str) -> None:
    print(f"PUT {local.name} -> {remote}")
    sftp.put(str(local), remote)


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
    nr = BACKEND / "nils_job_runtime"
    assert (nr / "turn_routing.py").is_file()

    digests = {name: sha256_file(nr / name) for name in MODULE_FILES if (nr / name).is_file()}
    meta = {
        "code_version": CODE_VERSION,
        "deployed_at": datetime.now(timezone.utc).isoformat(),
        "staging_db": STAGING_DB,
        "backup_root": BACKUP_ROOT,
        "digests": digests,
        "live_caps": LIVE_CAPS,
        "local_git_head": None,
        "note": "Isolated staging canary — not production CRM",
    }
    try:
        import subprocess

        meta["local_git_head"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(SERVER), text=True
        ).strip()
    except Exception:
        pass
    meta_path = SERVER / "scripts" / "_entity_routing_deploy_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    client = paramiko.SSHClient()
    ssh_connect(client, role="web")
    sftp = client.open_sftp()
    try:
        run(
            client,
            f"mkdir -p {REMOTE_BACKEND}/nils_job_runtime {REMOTE_SCRIPTS} "
            f"{REMOTE_DATA} {BACKUP_ROOT}/nils_job_runtime {BACKUP_ROOT}/env",
        )

        for name in MODULE_FILES:
            run(
                client,
                f"if [ -f {REMOTE_BACKEND}/nils_job_runtime/{name} ]; then "
                f"cp -a {REMOTE_BACKEND}/nils_job_runtime/{name} "
                f"{BACKUP_ROOT}/nils_job_runtime/{name}; fi",
            )
        run(client, f"cp -a /root/app/backend/.env {BACKUP_ROOT}/env/.env.bak")

        for name in MODULE_FILES:
            local = nr / name
            if local.is_file():
                sftp_put(sftp, local, f"{REMOTE_BACKEND}/nils_job_runtime/{name}")

        for fname in (
            "canary_nils_entity_routing_staging.py",
            "rollback_nils_entity_routing_staging.py",
            "_patch_env_entity_routing_staging.py",
        ):
            sftp_put(sftp, SERVER / "scripts" / fname, f"{REMOTE_SCRIPTS}/{fname}")
        sftp_put(sftp, meta_path, f"{BACKUP_ROOT}/deploy_meta.json")

        run(client, f"/root/app/venv/bin/python {REMOTE_SCRIPTS}/_patch_env_entity_routing_staging.py")

        run(
            client,
            rf"""mkdir -p /etc/systemd/system/nils-job-worker.service.d
cat > /etc/systemd/system/nils-job-worker.service.d/entity-routing-staging.conf <<'EOF'
[Service]
Environment=NILS_WORKER_LIVE_CAPABILITIES={LIVE_CAPS}
Environment=NILS_CAP_CRM_READ=1
Environment=NILS_CAP_CRM_PROSPECT_CREATE=1
Environment=NILS_CAP_EMAIL_SEND=0
Environment=NILS_CAP_N8N=0
Environment=NILS_CRM_BACKEND=sqlite
Environment=NILS_CRM_DB={STAGING_DB}
Environment=NILS_RUNTIME_CODE_VERSION={CODE_VERSION}
EnvironmentFile=-/root/app/backend/.env
ExecStart=
ExecStart=/root/app/venv/bin/python /root/app/scripts/nils_job_worker_cli.py --shadow-only --live-capabilities {LIVE_CAPS} --poll 1.0
EOF
systemctl daemon-reload
""",
        )

        run(client, "systemctl restart snack-api nils-job-worker")
        run(client, "sleep 2; systemctl is-active snack-api nils-job-worker")

        run(
            client,
            r"""cd /root/app/backend && /root/app/venv/bin/python - <<'PY'
import os
from pathlib import Path
for line in Path('.env').read_text().splitlines():
    if not line or line.startswith('#') or '=' not in line: continue
    k,_,v=line.partition('=')
    os.environ[k.strip()] = v
assert os.environ.get('NILS_CRM_BACKEND') == 'sqlite'
assert 'staging-entity' in (os.environ.get('NILS_CRM_DB') or '')
assert os.environ.get('NILS_CAP_EMAIL_SEND','1') == '0'
assert os.environ.get('NILS_CONTROL_PLANE_CANARY') == '1'
from nils_job_runtime import pipeline, turn_routing as tr
assert pipeline.map_capability('Lege Hassan Yassine als potentiellen Kunden an.')[0]=='crm.prospect_create'
assert pipeline.extract_company_from_text('Lege Hassan Yassine als potentiellen Kunden an.')=='Hassan Yassine'
g=tr.validate_intent_consistency('Lege Hassan an','crm.offer_read')
assert g.ok is False
print('SMOKE_ENTITY_ROUTING_OK', os.environ.get('NILS_RUNTIME_CODE_VERSION'))
print('ALLOWLIST_SET', bool(os.environ.get('NILS_CONTROL_PLANE_ALLOWLIST')))
PY""",
        )
    finally:
        sftp.close()
        client.close()

    print("DEPLOY_STAGING_OK", CODE_VERSION)
    print("BACKUP", BACKUP_ROOT)
    print("STAGING_DB", STAGING_DB)
    print("GIT_HEAD", meta.get("local_git_head"))
    print("DIGESTS", json.dumps(digests, indent=2)[:1500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

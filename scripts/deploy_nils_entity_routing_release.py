# -*- coding: utf-8 -*-
"""Immutable file-release deploy for Nils entity-routing (snack-api)."""
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


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(client, cmd: str, timeout: int = 180) -> str:
    print("+", cmd[:240])
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
    remote_release = f"/root/app/releases/{release_id}"
    remote_runtime = f"{remote_release}/nils_job_runtime"
    link = "/root/app/backend/nils_job_runtime"
    staging_db = f"/root/app/data/nils-crm-staging-entity-{short}.db"

    digests = {}
    for lp in sorted(local_nr.glob("*.py")):
        digests[lp.name] = sha256_file(lp)
    if (local_nr / "ggg_design_rules.json").is_file():
        digests["ggg_design_rules.json"] = sha256_file(local_nr / "ggg_design_rules.json")

    meta = {
        "release_id": release_id,
        "commit": commit,
        "code_version": code_version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "digests": digests,
        "staging_db": staging_db,
        "link": link,
        "remote_runtime": remote_runtime,
    }
    meta_path = SERVER / "scripts" / f"_release_meta_{short}.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    client = paramiko.SSHClient()
    ssh_connect(client, role="web")
    sftp = client.open_sftp()
    try:
        run(client, f"mkdir -p {remote_runtime} /root/app/releases /root/app/data /root/app/scripts")
        for name, _h in digests.items():
            sftp.put(str(local_nr / name), f"{remote_runtime}/{name}")
            print("PUT", name)
        sftp.put(str(meta_path), f"{remote_release}/digests.json")
        for fname in (
            "canary_nils_entity_routing_staging.py",
            "rollback_nils_entity_routing_staging.py",
            "_run_remote_entity_routing_final_canary.py",
            "_patch_env_release_flags.py",
        ):
            sftp.put(str(SERVER / "scripts" / fname), f"/root/app/scripts/{fname}")

        # Atomic switch
        run(
            client,
            f"set -e\n"
            f"if [ -L {link} ]; then rm -f {link}; "
            f"elif [ -d {link} ]; then mv {link} {link}.pre-{short}; fi\n"
            f"ln -sfn {remote_runtime} {link}\n"
            f"find {link} -name '__pycache__' -type d -prune -exec rm -rf {{}} +\n"
            f"find -L {link} -name '*.pyc' -delete\n"
            f"python3 -c \"import hashlib,json;from pathlib import Path;"
            f"m=json.loads(Path('{remote_release}/digests.json').read_text());"
            f"r=Path('{remote_runtime}');"
            f"bad=[n for n,e in m['digests'].items() if hashlib.sha256((r/n).read_bytes()).hexdigest()!=e];"
            f"assert not bad, bad; print('DIGEST_OK', len(m['digests']), m['commit'][:12])\"\n",
        )

        run(
            client,
            f"/root/app/venv/bin/python /root/app/scripts/_patch_env_release_flags.py "
            f"{code_version} {release_id} {commit}",
        )
        run(client, "systemctl restart snack-api nils-job-worker")
        run(client, "sleep 2; systemctl is-active snack-api nils-job-worker; readlink -f /root/app/backend/nils_job_runtime")
        run(
            client,
            "cd /root/app/backend && /root/app/venv/bin/python - <<'PY'\n"
            "import os\n"
            "from pathlib import Path\n"
            "for line in Path('.env').read_text().splitlines():\n"
            "    if not line or line.startswith('#') or '=' not in line: continue\n"
            "    k,_,v=line.partition('='); os.environ[k.strip()]=v\n"
            "from nils_job_runtime import pipeline\n"
            "assert pipeline.map_capability('Lege Max Mustermann als Ansprechpartner an.')[0]=='crm.prospect_create'\n"
            "assert pipeline.extract_contact_from_text('Lege Max Mustermann als Ansprechpartner an.')=='Max Mustermann'\n"
            "assert pipeline.extract_company_from_text('Lege Max Mustermann als Ansprechpartner an.')==''\n"
            "assert pipeline.map_capability('Lege Hassan Yassine als potentiellen Kunden an.')[0]=='crm.prospect_create'\n"
            "print('SMOKE_RELEASE_OK', os.environ.get('NILS_RELEASE_ID'), os.environ.get('NILS_GIT_COMMIT','')[:12])\n"
            "print('PROSPECT_CAP', os.environ.get('NILS_CAP_CRM_PROSPECT_CREATE'))\n"
            "print('CRM_BACKEND', os.environ.get('NILS_CRM_BACKEND'))\n"
            "PY",
        )
    finally:
        sftp.close()
        client.close()

    print("RELEASE_DEPLOY_OK", release_id, commit)
    print("STAGING_DB_FOR_CANARY", staging_db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

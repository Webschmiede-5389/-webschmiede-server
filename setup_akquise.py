#!/usr/bin/env python3
"""Install Akquise-Krieger on Hetzner: files + nightly cron + nginx route."""
import os
import sys

import paramiko

sys.path.insert(0, os.path.dirname(__file__))
from agency_config import load_secrets, ssh_connect
from deploy_shell import upload_shell_script, verify_remote_shell

HOST = load_secrets()["SERVER_HOST"]
REMOTE_ROOT = "/root/app"
WEBROOT = "/var/www/snackhouse-mechernich"
NGINX_SITE = "/etc/nginx/sites-available/snack-house"

# Wrapper-Script lädt Places-Key sicher (kein leeres $() beim crontab-Install)
CRON_GASTRO = "0 2 * * * /bin/bash /root/app/scripts/akquise_nightly.sh gastro >> /var/log/akquise.log 2>&1"
CRON_HANDWERK = "30 3 * * * /bin/bash /root/app/scripts/akquise_nightly.sh handwerk >> /var/log/akquise.log 2>&1"

LOCAL_ROOT = os.path.dirname(__file__)
UPLOAD_DIRS = ["akquise", "scripts"]
UPLOAD_FILES = [
    ("scripts/akquise_scan.py", f"{REMOTE_ROOT}/scripts/akquise_scan.py"),
    ("scripts/akquise_run.py", f"{REMOTE_ROOT}/scripts/akquise_run.py"),
    ("scripts/akquise_nightly.sh", f"{REMOTE_ROOT}/scripts/akquise_nightly.sh"),
]

NGINX_AKQUISE = """
    # Akquise report (passwortgeschuetzt optional — intern)
    location = /akquise {
        try_files /akquise-report.html =404;
    }
"""


def run(client, cmd, timeout=60):
    _, out, err = client.exec_command(cmd, timeout=timeout)
    o = out.read().decode("utf-8", errors="replace").strip()
    e = err.read().decode("utf-8", errors="replace").strip()
    if o:
        print(o)
    if e and "WARNING" not in e.upper():
        print("ERR:", e[:400])
    return o


def upload_tree(sftp, local, remote):
    for root, dirs, files in os.walk(local):
        rel = os.path.relpath(root, local).replace("\\", "/")
        remote_dir = remote if rel == "." else f"{remote}/{rel}"
        try:
            sftp.mkdir(remote_dir)
        except OSError:
            pass
        for f in files:
            if f.endswith(".pyc"):
                continue
            lp = os.path.join(root, f)
            rp = f"{remote_dir}/{f}"
            print(f"  {os.path.relpath(lp, LOCAL_ROOT)}")
            if f.endswith(".sh"):
                upload_shell_script(sftp, lp, rp)
            else:
                sftp.put(lp, rp)


def main():
    client = paramiko.SSHClient()
    ssh_connect(client)

    print("=== Verzeichnisse ===")
    run(client, f"mkdir -p {REMOTE_ROOT}/akquise {REMOTE_ROOT}/scripts {REMOTE_ROOT}/docs/akquise/reports")

    sftp = client.open_sftp()
    for d in UPLOAD_DIRS:
        local = os.path.join(LOCAL_ROOT, d)
        remote = f"{REMOTE_ROOT}/{d}"
        if os.path.isdir(local):
            print(f"Upload {d}/")
            upload_tree(sftp, local, remote)

    for local_rel, remote in UPLOAD_FILES:
        lp = os.path.join(LOCAL_ROOT, local_rel.replace("/", os.sep))
        if os.path.isfile(lp):
            print(f"Upload {local_rel}")
            upload_shell_script(sftp, lp, remote)

    report = os.path.join(LOCAL_ROOT, "app", "static", "akquise-report.html")
    if os.path.isfile(report):
        sftp.put(report, f"{WEBROOT}/akquise-report.html")
    sftp.close()

    print("\n=== Python deps ===")
    run(client, "pip3 install requests -q 2>/dev/null || apt-get install -y -qq python3-requests 2>/dev/null || true")

    # Secrets für Places (Portal speichert hier)
    run(
        client,
        f"test -f {REMOTE_ROOT}/deploy.secrets.local || "
        f"cp {REMOTE_ROOT}/backend/../deploy.secrets.local {REMOTE_ROOT}/deploy.secrets.local 2>/dev/null || true; "
        f"grep -q '^GOOGLE_PLACES_API_KEY=' {REMOTE_ROOT}/deploy.secrets.local 2>/dev/null && "
        f"echo places_key=yes || echo places_key=missing",
    )

    run(client, f"chmod +x {REMOTE_ROOT}/scripts/akquise_nightly.sh")
    ok, msg = verify_remote_shell(client, f"{REMOTE_ROOT}/scripts/akquise_nightly.sh")
    if not ok:
        raise RuntimeError(f"akquise_nightly.sh Syntax-Fehler: {msg}")
    print("script_syntax_ok")
    print("\n=== Cron Nacht (02:00 gastro, 03:30 handwerk) ===")
    run(
        client,
        "("
        "crontab -l 2>/dev/null | grep -v akquise || true; "
        f"echo '{CRON_GASTRO}'; "
        f"echo '{CRON_HANDWERK}'"
        ") | crontab -",
    )
    run(client, "crontab -l | grep akquise || true")

    print("\n=== nginx /akquise ===")
    nginx = run(client, f"cat {NGINX_SITE}")
    if "location = /akquise" not in nginx:
        marker = "    location = /seminare {"
        if marker in nginx:
            nginx = nginx.replace(marker, NGINX_AKQUISE + marker)
        elif "    # Webschmiede Agency" in nginx:
            nginx = nginx.replace("    # Webschmiede Agency", NGINX_AKQUISE + "\n    # Webschmiede Agency")
        else:
            nginx = nginx.replace("    location /api/ {", NGINX_AKQUISE + "\n    location /api/ {")
        sftp = client.open_sftp()
        with sftp.open(NGINX_SITE, "w") as f:
            f.write(nginx)
        sftp.close()
        run(client, "nginx -t && systemctl reload nginx")

    print("\n=== Smoke: Places-Key + Script import ===")
    run(
        client,
        f"cd {REMOTE_ROOT} && "
        f"export GOOGLE_PLACES_API_KEY=$(grep ^GOOGLE_PLACES_API_KEY= deploy.secrets.local | cut -d= -f2-) && "
        f"python3 -c \"from pathlib import Path; import sys; sys.path.insert(0,'akquise'); "
        f"from places import load_api_key; k=load_api_key(); print('key', bool(k), 'len', len(k or ''))\"",
    )

    client.close()
    print("\n=== FERTIG ===")
    print(f"Report: http://{HOST}/akquise")
    print("Cron: 02:00 gastro, 03:30 handwerk -> /var/log/akquise.log")
    print("Places: deploy.secrets.local GOOGLE_PLACES_API_KEY")


if __name__ == "__main__":
    main()

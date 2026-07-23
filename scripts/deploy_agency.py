#!/usr/bin/env python3

"""Deploy agency website (digitalehandwerkskunst.de) to Hetzner."""

import os

import sys



import paramiko



sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agency_config import load_secrets, ssh_connect



ROOT = os.path.dirname(os.path.dirname(__file__))

HOST = load_secrets()["SERVER_HOST"]

REMOTE_WEBROOT = "/var/www/digitalehandwerkskunst"

STATIC = os.path.join(ROOT, "app", "static")



LOCAL_CANDIDATES = [

    os.path.join(ROOT, "agency-web", "dist"),

    os.path.join(ROOT, "agency-web", "build"),

    os.path.join(ROOT, "agency-web", "dist-backup"),

]



EXTRA_FILES = [

    ("angebote.html", os.path.join(ROOT, "agency-web", "public", "angebote.html")),

    ("angebote.json", os.path.join(ROOT, "agency-web", "public", "angebote.json")),

]





def find_source() -> str:

    for path in LOCAL_CANDIDATES:

        if os.path.isfile(os.path.join(path, "index.html")):

            return path

    raise SystemExit(

        "Kein Agency-Build gefunden. Erwartet: agency-web/dist/\n"

        "  cd agency-web && npm run build"

    )





def upload_tree(sftp, local_dir: str, remote_dir: str):

    for name in os.listdir(local_dir):

        local = os.path.join(local_dir, name)

        remote = f"{remote_dir}/{name}"

        if os.path.isdir(local):

            try:

                sftp.mkdir(remote)

            except OSError:

                pass

            upload_tree(sftp, local, remote)

        else:

            print(f"  {name}")

            sftp.put(local, remote)





def upload_ci(sftp, remote_webroot: str):

    ci_local = os.path.join(STATIC, "ci")

    if not os.path.isdir(ci_local):

        return

    remote_ci = f"{remote_webroot}/ci"

    try:

        sftp.mkdir(remote_ci)

    except OSError:

        pass

    for name in os.listdir(ci_local):

        local = os.path.join(ci_local, name)

        if os.path.isfile(local):

            print(f"  ci/{name}")

            sftp.put(local, f"{remote_ci}/{name}")





def main():

    local = find_source()

    print(f"Deploy Agency-Site: {local}")

    print(f"  -> {HOST}:{REMOTE_WEBROOT}\n")



    client = paramiko.SSHClient()

    ssh_connect(client, timeout=45, banner_timeout=45, role="web")

    client.exec_command(f"mkdir -p {REMOTE_WEBROOT}")



    sftp = client.open_sftp()

    upload_tree(sftp, local, REMOTE_WEBROOT)



    print("\nExtra: Angebote & CI")

    for remote_name, local_path in EXTRA_FILES:

        if os.path.isfile(local_path):

            print(f"  {remote_name}")

            sftp.put(local_path, f"{REMOTE_WEBROOT}/{remote_name}")

    upload_ci(sftp, REMOTE_WEBROOT)

    sftp.close()



    _, out, _ = client.exec_command(

        f"chown -R www-data:www-data {REMOTE_WEBROOT} 2>/dev/null || "

        f"chown -R nginx:nginx {REMOTE_WEBROOT} 2>/dev/null || true"

    )

    out.read()



    _, out, _ = client.exec_command(

        f'curl -s -o /dev/null -w "angebote.html HTTP %{{http_code}}\\n" '

        f'-H "Host: digitalehandwerkskunst.de" http://127.0.0.1/angebote.html; '

        f'test -f {REMOTE_WEBROOT}/angebote.json && echo "angebote.json: ok" || echo "angebote.json: MISSING"'

    )

    print(out.read().decode().strip())



    client.close()

    print("\nDeploy fertig: https://digitalehandwerkskunst.de/angebote.html")





if __name__ == "__main__":

    main()


#!/usr/bin/env python3
"""Deploy Dark Plurality + Quoka + Demand-Scan auf auto-01."""
import os
import sys

import paramiko

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agency_config import ssh_connect

ROOT = os.path.dirname(os.path.dirname(__file__))
FILES = [
    ("akquise/quoka.py", "/root/app/akquise/quoka.py"),
    ("akquise/nexxt_change.py", "/root/app/akquise/nexxt_change.py"),
    ("akquise/forums.py", "/root/app/akquise/forums.py"),
    ("akquise/dark_sources.py", "/root/app/akquise/dark_sources.py"),
    ("akquise/dark_sources.json", "/root/app/akquise/dark_sources.json"),
    ("akquise/demand.py", "/root/app/akquise/demand.py"),
    ("akquise/kleinanzeigen.py", "/root/app/akquise/kleinanzeigen.py"),
    ("akquise/directories.py", "/root/app/akquise/directories.py"),
    ("akquise/verticals/trockenbau.json", "/root/app/akquise/verticals/trockenbau.json"),
    ("akquise/verticals/fliesenleger.json", "/root/app/akquise/verticals/fliesenleger.json"),
    ("akquise/verticals/gartenbau.json", "/root/app/akquise/verticals/gartenbau.json"),
    ("akquise/verticals/hochbau.json", "/root/app/akquise/verticals/hochbau.json"),
    ("akquise/verticals/tiefbau.json", "/root/app/akquise/verticals/tiefbau.json"),
    ("docs/akquise/forums.md", "/root/app/docs/akquise/forums.md"),
    ("docs/akquise/krieger.md", "/root/app/docs/akquise/krieger.md"),
    ("scripts/akquise_demand_scan.py", "/root/app/scripts/akquise_demand_scan.py"),
    ("scripts/akquise_nightly.sh", "/root/app/scripts/akquise_nightly.sh"),
]


def main():
    c = paramiko.SSHClient()
    ssh_connect(c, timeout=30, banner_timeout=30, role="auto")
    c.exec_command(
        "mkdir -p /root/app/akquise/verticals /root/app/docs/akquise /root/app/scripts"
    )
    sftp = c.open_sftp()
    for local_rel, remote in FILES:
        lp = os.path.join(ROOT, local_rel.replace("/", os.sep))
        if not os.path.isfile(lp):
            print(f"SKIP missing: {local_rel}")
            continue
        print(f"Upload {local_rel}")
        if local_rel.endswith(".sh"):
            from deploy_shell import upload_shell_script

            upload_shell_script(sftp, lp, remote)
        else:
            sftp.put(lp, remote)
    sftp.close()

    _, o, e = c.exec_command(
        "cd /root/app/akquise && python3 -c \""
        "from quoka import VERTICAL_SEARCHES; from nexxt_change import NACE; "
        "from dark_sources import catalog_summary; "
        "bau=['trockenbau','fliesenleger','gartenbau','hochbau','tiefbau']; "
        "print('quoka_bau', all(v in VERTICAL_SEARCHES for v in bau)); "
        "print('nexxt_bau', all(v in NACE for v in bau)); "
        "n=__import__('nexxt_change').scan_nexxt(verticals=['fliesenleger','gartenbau'], pause_s=0.7); "
        "print('smoke_nexxt_bau', len(n)); "
        "print('catalog', catalog_summary())"
        "\"",
        timeout=180,
    )
    print((o.read() + e.read()).decode("utf-8", "replace"))
    c.close()
    print("OK dark+quoka on auto-01")


if __name__ == "__main__":
    main()

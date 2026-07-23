#!/usr/bin/env python3
"""Deploy Akquise Engine (alle Verticals) zum Server."""
import os
import sys

import paramiko

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agency_config import ssh_connect

ROOT = os.path.dirname(os.path.dirname(__file__))
FILES = [
    ("akquise/__init__.py", "/root/app/akquise/__init__.py"),
    ("akquise/engine.py", "/root/app/akquise/engine.py"),
    ("akquise/discover.py", "/root/app/akquise/discover.py"),
    ("akquise/enrichment.py", "/root/app/akquise/enrichment.py"),
    ("akquise/intent.py", "/root/app/akquise/intent.py"),
    ("akquise/providers.py", "/root/app/akquise/providers.py"),
    ("akquise/budget.py", "/root/app/akquise/budget.py"),
    ("akquise/problems.py", "/root/app/akquise/problems.py"),
    ("akquise/revenue.py", "/root/app/akquise/revenue.py"),
    ("akquise/openness.py", "/root/app/akquise/openness.py"),
    ("akquise/competition.py", "/root/app/akquise/competition.py"),
    ("akquise/diff.py", "/root/app/akquise/diff.py"),
    ("akquise/meta_ads.py", "/root/app/akquise/meta_ads.py"),
    ("akquise/register.py", "/root/app/akquise/register.py"),
    ("akquise/places.py", "/root/app/akquise/places.py"),
    ("akquise/quoka.py", "/root/app/akquise/quoka.py"),
    ("akquise/nexxt_change.py", "/root/app/akquise/nexxt_change.py"),
    ("akquise/forums.py", "/root/app/akquise/forums.py"),
    ("akquise/dark_sources.py", "/root/app/akquise/dark_sources.py"),
    ("akquise/dark_sources.json", "/root/app/akquise/dark_sources.json"),
    ("akquise/demand.py", "/root/app/akquise/demand.py"),
    ("akquise/kleinanzeigen.py", "/root/app/akquise/kleinanzeigen.py"),
    ("akquise/settings.json", "/root/app/akquise/settings.json"),
    ("akquise/config.json", "/root/app/akquise/config.json"),
    ("akquise/verticals/gastro.json", "/root/app/akquise/verticals/gastro.json"),
    ("akquise/verticals/handwerk.json", "/root/app/akquise/verticals/handwerk.json"),
    ("akquise/verticals/dental.json", "/root/app/akquise/verticals/dental.json"),
    ("akquise/verticals/dach.json", "/root/app/akquise/verticals/dach.json"),
    ("akquise/verticals/friseur.json", "/root/app/akquise/verticals/friseur.json"),
    ("akquise/verticals/trockenbau.json", "/root/app/akquise/verticals/trockenbau.json"),
    ("akquise/verticals/fliesenleger.json", "/root/app/akquise/verticals/fliesenleger.json"),
    ("akquise/verticals/gartenbau.json", "/root/app/akquise/verticals/gartenbau.json"),
    ("akquise/verticals/hochbau.json", "/root/app/akquise/verticals/hochbau.json"),
    ("akquise/verticals/tiefbau.json", "/root/app/akquise/verticals/tiefbau.json"),
    ("akquise/verticals/elektro.json", "/root/app/akquise/verticals/elektro.json"),
    ("scripts/akquise_scan.py", "/root/app/scripts/akquise_scan.py"),
    ("scripts/akquise_run.py", "/root/app/scripts/akquise_run.py"),
    ("scripts/akquise_export.py", "/root/app/scripts/akquise_export.py"),
]


def main():
    c = paramiko.SSHClient()
    ssh_connect(c, timeout=30, banner_timeout=30)
    c.exec_command("mkdir -p /root/app/akquise/verticals /root/app/docs/akquise/reports")
    sftp = c.open_sftp()
    for local_rel, remote in FILES:
        lp = os.path.join(ROOT, local_rel.replace("/", os.sep))
        if not os.path.isfile(lp):
            print(f"SKIP (missing): {local_rel}")
            continue
        print(f"Upload {local_rel}")
        sftp.put(lp, remote)
    sftp.close()
    print("Start gastro scan (background)...")
    c.exec_command(
        "cd /root/app && nohup python3 scripts/akquise_run.py --vertical gastro --workers 6 "
        ">> /var/log/akquise-v3.log 2>&1 &"
    )
    c.close()
    print("OK — Scan laeuft. Log: /var/log/akquise-v3.log")


if __name__ == "__main__":
    main()

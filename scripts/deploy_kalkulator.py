#!/usr/bin/env python3
"""Hot-deploy Kalkulator JSON + agency.html."""
import os
import sys

import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency_config import ssh_connect

client = paramiko.SSHClient()
ssh_connect(client, timeout=45, banner_timeout=45, role="web")
client.exec_command("mkdir -p /root/app/data")
sftp = client.open_sftp()
for loc, rem in [
    ("app/data/kalkulator-preise.json", "/root/app/data/kalkulator-preise.json"),
    ("app/static/agency.html", "/root/app/static/agency.html"),
]:
    local = os.path.join(ROOT, loc.replace("/", os.sep))
    print("put", loc)
    sftp.put(local, rem)
sftp.close()


def run(cmd: str) -> None:
    _, out, err = client.exec_command(cmd, timeout=90)
    text = (out.read() + err.read()).decode("utf-8", "replace").strip()
    if text:
        print(text)


run("cp /root/app/static/agency.html /var/www/snackhouse-mechernich/agency.html")
run("cp /root/app/static/agency.html /var/www/digitalehandwerkskunst/agency.html 2>/dev/null || true")
run("systemctl restart snack-api")
run("systemctl is-active snack-api")
run(
    "python3 -c \"import json;d=json.load(open('/root/app/data/kalkulator-preise.json'));"
    "print('v',d['version'],'kern',d['kern_setup']['price_eur'],'pakete',len(d['retainer_pakete']))\""
)
client.close()
print("OK")

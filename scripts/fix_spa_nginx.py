#!/usr/bin/env python3
"""Add SPA try_files for React routes on digitalehandwerkskunst.de."""
import os
import sys

import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency_config import ssh_connect

# Safe SPA locations – only known React routes, don't break static html
SNIPPET = r"""
    # React SPA routes (agency-web)
    location = /anbindungen {
        try_files /index.html =404;
    }
    location = /impressum {
        try_files /index.html =404;
    }
    location = /datenschutz {
        try_files /index.html =404;
    }
    location = /markenhinweise {
        try_files /index.html =404;
    }
    location = /support {
        try_files /index.html =404;
    }
"""

client = paramiko.SSHClient()
ssh_connect(client, timeout=60, banner_timeout=60, role="web")


def run(cmd: str, timeout: int = 60) -> str:
    _, out, err = client.exec_command(cmd, timeout=timeout)
    return (out.read() + err.read()).decode("utf-8", "replace", errors="replace")


# backup
print(run("cp /etc/nginx/sites-enabled/digitalehandwerkskunst.de /root/digitalehandwerkskunst.de.bak.$(date +%Y%m%d%H%M)"))

conf = run("cat /etc/nginx/sites-enabled/digitalehandwerkskunst.de")
if "location = /anbindungen" in conf:
    print("SPA locations already present")
else:
    # Insert after server_name / root block – before first location
    marker = "location "
    idx = conf.find(marker)
    if idx < 0:
        raise SystemExit("no location block found")
    new_conf = conf[:idx] + SNIPPET + "\n" + conf[idx:]
    sftp = client.open_sftp()
    with sftp.file("/tmp/dhk-nginx.conf", "w") as f:
        f.write(new_conf)
    sftp.close()
    print(
        run(
            "cp /tmp/dhk-nginx.conf /etc/nginx/sites-enabled/digitalehandwerkskunst.de && "
            "nginx -t && systemctl reload nginx"
        )
    )

print(run("curl -sI https://digitalehandwerkskunst.de/anbindungen | head -15"))
print(run("curl -sI https://digitalehandwerkskunst.de/ | head -10"))
print(run("curl -s https://digitalehandwerkskunst.de/ | grep -o 'Gespräch buchen\\|Kurz klären\\|Vier Stufen\\|Support mit SLA\\|Automatisierungs' | sort | uniq -c"))
client.close()

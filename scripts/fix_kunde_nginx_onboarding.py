"""Fix nested /onboarding inside /admin in kunde-* nginx configs."""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect

ONBOARDING = """    location = /onboarding {
        try_files /onboarding.html =404;
    }"""

client = paramiko.SSHClient()
ssh_connect(client)
_, out, _ = client.exec_command(
    "ls /etc/nginx/sites-available/kunde-*.digitalehandwerkskunst.de 2>/dev/null"
)
sites = [s.strip() for s in out.read().decode().splitlines() if s.strip()]
sftp = client.open_sftp()

for site in sites:
    with sftp.open(site, "r") as f:
        cfg = f.read().decode("utf-8")
    orig = cfg

    # Remove wrongly nested onboarding block inside /admin
    cfg = re.sub(
        r"(location = /admin \{\n)\s*location = /onboarding \{[^}]+\}\s*",
        r"\1",
        cfg,
        count=1,
    )

    # Ensure onboarding exists as sibling after admin block
    if "location = /onboarding" not in cfg:
        cfg = cfg.replace(
            "    location = /admin {\n        try_files /admin.html =404;\n    }",
            "    location = /admin {\n        try_files /admin.html =404;\n    }\n"
            + ONBOARDING,
            1,
        )

    if cfg != orig:
        with sftp.open(site, "w") as f:
            f.write(cfg)
        print("FIXED", site)
    else:
        print("OK", site)

sftp.close()
_, out, err = client.exec_command("nginx -t 2>&1")
result = out.read().decode() + err.read().decode()
print(result)
if "successful" in result:
    client.exec_command("systemctl reload nginx")
    print("nginx reloaded")
client.close()

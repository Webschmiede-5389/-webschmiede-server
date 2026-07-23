#!/usr/bin/env python3
"""Copy Cal.com Postgres volume from old Helsinki web to web-01neu."""
import sys
from pathlib import Path
import paramiko

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agency_config import _read_file_secrets, target_secrets

OLD = "204.168.170.97"
LOCAL = ROOT / "tmp_calcom_pg.tgz"


def connect(ip, pw):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(ip, username="root", password=pw, timeout=30, look_for_keys=False, allow_agent=False)
    return c


def run(c, cmd, t=600):
    _, o, e = c.exec_command(cmd, timeout=t)
    code = o.channel.recv_exit_status()
    return code, (o.read() + e.read()).decode("utf-8", "replace")


secrets = _read_file_secrets()
old_pw = secrets.get("OLD_WEB_PASSWORD") or secrets.get("WEB_PASSWORD") or secrets.get("SERVER_PASSWORD", "")
new = target_secrets("web")
new_ip, new_pw = new["SERVER_HOST"], new["SERVER_PASSWORD"]

old = connect(OLD, old_pw)
code, text = run(old, "docker volume inspect calcom_cal_pg >/dev/null 2>&1 && echo yes || echo no")
if "yes" not in text:
    print("Kein calcom volume auf altem Server — frisches Cal.com")
    old.close()
    sys.exit(0)

run(
    old,
    "docker run --rm -v calcom_cal_pg:/v -v /tmp:/tmp alpine tar czf /tmp/calcom-pg.tgz -C /v .",
    t=300,
)
sftp = old.open_sftp()
sftp.get("/tmp/calcom-pg.tgz", str(LOCAL))
sftp.close()
run(old, "rm -f /tmp/calcom-pg.tgz")
old.close()

n = connect(new_ip, new_pw)
run(n, "docker volume create calcom_cal_pg")
sftp_n = n.open_sftp()
sftp_n.put(str(LOCAL), "/tmp/calcom-pg.tgz")
sftp_n.close()
LOCAL.unlink(missing_ok=True)
run(
    n,
    "docker run --rm -v calcom_cal_pg:/v -v /tmp:/tmp alpine sh -c 'cd /v && tar xzf /tmp/calcom-pg.tgz'",
    t=300,
)
run(n, "rm -f /tmp/calcom-pg.tgz")
run(n, "cd /opt/calcom && docker compose up -d")
_, o, _ = n.exec_command("curl -sf -o /dev/null -w '%{http_code}' http://127.0.0.1:3000/ || echo fail")
print("Cal.com HTTP:", o.read().decode())
n.close()
print("OK Cal.com migriert")

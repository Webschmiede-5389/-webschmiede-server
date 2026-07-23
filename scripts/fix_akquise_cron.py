"""Akquise-Nacht-Cron korrekt setzen (ohne leeren Places-Key)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agency_config import ssh_connect
from deploy_shell import upload_shell_script, verify_remote_shell
import paramiko

ROOT = Path(__file__).resolve().parents[1]
LOCAL_SH = ROOT / "scripts" / "akquise_nightly.sh"
REMOTE_SH = "/root/app/scripts/akquise_nightly.sh"

c = paramiko.SSHClient()
ssh_connect(c, timeout=25)
sftp = c.open_sftp()
upload_shell_script(sftp, LOCAL_SH, REMOTE_SH)
sftp.close()


def run(cmd, timeout=60):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    print((o.read() + e.read()).decode("utf-8", "replace").encode("ascii", "replace").decode())


run(f"chmod +x {REMOTE_SH}")
ok, msg = verify_remote_shell(c, REMOTE_SH)
if not ok:
    raise SystemExit(f"Syntax-Fehler: {msg}")
print("script_syntax_ok")
run(
    "("
    "crontab -l 2>/dev/null | grep -v akquise || true; "
    "echo '0 2 * * * /root/app/scripts/akquise_nightly.sh gastro'; "
    "echo '30 3 * * * /root/app/scripts/akquise_nightly.sh handwerk'"
    ") | crontab -"
)
run("crontab -l")
run(
    "test -f /root/app/deploy.secrets.local && grep -c '^GOOGLE_PLACES_API_KEY=' /root/app/deploy.secrets.local "
    "|| echo missing_secrets"
)
# quick dry: run script header only
run("head -5 /root/app/scripts/akquise_nightly.sh")
c.close()
print("OK")

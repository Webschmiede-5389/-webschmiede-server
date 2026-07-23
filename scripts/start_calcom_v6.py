"""Cal.com Compose auf Server auf v6.2.0 bringen und starten."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agency_config import ssh_connect
import paramiko

CAL_DIR = "/opt/calcom"
IMAGE = "calcom/cal.com:v6.2.0"

c = paramiko.SSHClient()
ssh_connect(c, timeout=25, banner_timeout=25)


def run(cmd, timeout=600):
    print(">>>", cmd[:100])
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    if out.strip():
        print(out[-3000:])
    if err.strip() and "WARNING" not in err.upper():
        print("ERR:", err[-2000:])
    return out, err


# Compose-Datei Image-Tag aktualisieren (falls schon da)
run(
    f"test -f {CAL_DIR}/docker-compose.yml && "
    f"sed -i 's|calcom/cal.com:.*|calcom/cal.com:v6.2.0|' {CAL_DIR}/docker-compose.yml && "
    f"grep image {CAL_DIR}/docker-compose.yml || echo NO_COMPOSE"
)

# Falls Compose fehlt: Script setup_calcom erneut – hier nur Start, falls vorhanden
out, _ = run(f"test -f {CAL_DIR}/docker-compose.yml && echo HAS || echo MISSING")
if "MISSING" in out:
    print("Compose fehlt – bitte setup_calcom.py erneut ausführen.")
    c.close()
    sys.exit(1)

print("=== Pull + Up ===")
run(f"cd {CAL_DIR} && docker compose pull", timeout=900)
run(f"cd {CAL_DIR} && docker compose up -d", timeout=300)
run("sleep 20 && docker compose -f /opt/calcom/docker-compose.yml ps")
run("curl -sI -m 15 http://127.0.0.1:3000/ | head -15 || true")
run("curl -sI -m 15 http://127.0.0.1/cal/ | head -15 || true")

c.close()
print("DONE")

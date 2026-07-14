"""Load deploy SSH credentials from env or gitignored deploy.secrets.local."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SECRETS_FILE = ROOT / "deploy.secrets.local"

DEFAULT_HOST = "167.233.211.170"
DEFAULT_USER = "root"


def load_secrets() -> dict:
    values: dict[str, str] = {}
    if SECRETS_FILE.exists():
        for line in SECRETS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            values[key.strip()] = val.strip()

    host = os.environ.get("WEBSCHMIEDE_SERVER_HOST") or values.get("SERVER_HOST", DEFAULT_HOST)
    user = os.environ.get("WEBSCHMIEDE_SERVER_USER") or values.get("SERVER_USER", DEFAULT_USER)
    password = os.environ.get("WEBSCHMIEDE_SSH_PASSWORD") or values.get("SERVER_PASSWORD")
    if not password:
        raise RuntimeError(
            f"SERVER_PASSWORD fehlt. Datei anlegen: {SECRETS_FILE.name} "
            f"(Vorlage: deploy.secrets.local.example)"
        )
    return {"SERVER_HOST": host, "SERVER_USER": user, "SERVER_PASSWORD": password}


def ssh_connect(client, timeout=20, banner_timeout=20):
    import paramiko

    s = load_secrets()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        s["SERVER_HOST"],
        username=s["SERVER_USER"],
        password=s["SERVER_PASSWORD"],
        timeout=timeout,
        look_for_keys=False,
        allow_agent=False,
        banner_timeout=banner_timeout,
    )
    return s

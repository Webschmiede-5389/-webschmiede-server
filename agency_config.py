"""Load deploy SSH credentials from env or gitignored deploy.secrets.local."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SECRETS_FILE = ROOT / "deploy.secrets.local"

DEFAULT_HOST = "167.233.211.170"
DEFAULT_USER = "root"


def _read_file_secrets() -> dict[str, str]:
    values: dict[str, str] = {}
    if SECRETS_FILE.exists():
        for line in SECRETS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            values[key.strip()] = val.strip()
    return values


def load_secrets() -> dict:
    """Default SSH target: alter Server (Migration-Quelle) oder WEBSCHMIEDE_SERVER_HOST."""
    values = _read_file_secrets()
    host = os.environ.get("WEBSCHMIEDE_SERVER_HOST") or values.get("SERVER_HOST", DEFAULT_HOST)
    user = os.environ.get("WEBSCHMIEDE_SERVER_USER") or values.get("SERVER_USER", DEFAULT_USER)
    password = os.environ.get("WEBSCHMIEDE_SSH_PASSWORD") or values.get("SERVER_PASSWORD")
    if not password:
        raise RuntimeError(
            f"SERVER_PASSWORD fehlt. Datei anlegen: {SECRETS_FILE.name} "
            f"(Vorlage: deploy.secrets.local.example)"
        )
    out = dict(values)
    out.update({"SERVER_HOST": host, "SERVER_USER": user, "SERVER_PASSWORD": password})
    return out


def target_secrets(role: str = "old") -> dict:
    """role: old | web | auto | voice"""
    values = load_secrets()
    user = values.get("SERVER_USER", DEFAULT_USER)
    if role == "web":
        host = values.get("WEB_HOST")
        password = values.get("WEB_PASSWORD") or values.get("SERVER_PASSWORD")
    elif role == "auto":
        host = values.get("AUTO_HOST")
        password = values.get("AUTO_PASSWORD") or values.get("SERVER_PASSWORD")
    elif role == "voice":
        host = values.get("VOICE_HOST") or values.get("AUTO_HOST")
        password = (
            values.get("VOICE_PASSWORD")
            or values.get("AUTO_PASSWORD")
            or values.get("SERVER_PASSWORD")
        )
    else:
        host = values.get("SERVER_HOST", DEFAULT_HOST)
        password = values.get("SERVER_PASSWORD")
    if not host or not password:
        raise RuntimeError(f"Host/Passwort für role={role} fehlt in {SECRETS_FILE.name}")
    return {"SERVER_HOST": host, "SERVER_USER": user, "SERVER_PASSWORD": password}


def ssh_connect(client, timeout=20, banner_timeout=20, role: str = "old"):
    import paramiko

    s = target_secrets(role)
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

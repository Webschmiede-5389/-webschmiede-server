"""Load deploy SSH credentials from env or gitignored deploy.secrets.local."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SECRETS_FILE = ROOT / "deploy.secrets.local"

# Aktueller Web-Server (nach CX33-Cutover)
DEFAULT_HOST = "167.233.150.230"
# Alter Helsinki-Server (offline / nur Migration)
LEGACY_OLD_HOST = "167.233.211.170"
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
    """Secrets + operativer Default-Host (WEB_HOST, sonst SERVER_HOST)."""
    values = _read_file_secrets()
    user = os.environ.get("WEBSCHMIEDE_SERVER_USER") or values.get("SERVER_USER", DEFAULT_USER)
    password = (
        os.environ.get("WEBSCHMIEDE_SSH_PASSWORD")
        or values.get("WEB_PASSWORD")
        or values.get("SERVER_PASSWORD")
    )
    if not password:
        raise RuntimeError(
            f"SERVER_PASSWORD/WEB_PASSWORD fehlt. Datei anlegen: {SECRETS_FILE.name} "
            f"(Vorlage: deploy.secrets.local.example)"
        )
    out = dict(values)
    # Rohwerte für role=old behalten
    if values.get("SERVER_HOST"):
        out["OLD_SERVER_HOST"] = values["SERVER_HOST"]
    # Operativer Default: WEB_HOST (Live), Fallback SERVER_HOST, dann DEFAULT
    host = (
        os.environ.get("WEBSCHMIEDE_SERVER_HOST")
        or values.get("WEB_HOST")
        or values.get("SERVER_HOST")
        or DEFAULT_HOST
    )
    out.update({"SERVER_HOST": host, "SERVER_USER": user, "SERVER_PASSWORD": password})
    return out


def target_secrets(role: str = "web") -> dict:
    """role: web | auto | voice | old

    Default ist **web** (Live). role=old nur für Migration vom Alt-Server.
    """
    raw = _read_file_secrets()
    values = load_secrets()
    user = values.get("SERVER_USER", DEFAULT_USER)
    if role == "web":
        host = raw.get("WEB_HOST") or values.get("WEB_HOST") or DEFAULT_HOST
        password = raw.get("WEB_PASSWORD") or values.get("SERVER_PASSWORD")
    elif role == "auto":
        host = raw.get("AUTO_HOST") or values.get("AUTO_HOST")
        password = (
            raw.get("AUTO_PASSWORD")
            or raw.get("WEB_PASSWORD")
            or values.get("SERVER_PASSWORD")
        )
    elif role == "voice":
        host = raw.get("VOICE_HOST") or raw.get("AUTO_HOST") or values.get("AUTO_HOST")
        password = (
            raw.get("VOICE_PASSWORD")
            or raw.get("AUTO_PASSWORD")
            or raw.get("WEB_PASSWORD")
            or values.get("SERVER_PASSWORD")
        )
    elif role == "old":
        host = raw.get("SERVER_HOST") or values.get("OLD_SERVER_HOST") or LEGACY_OLD_HOST
        password = raw.get("SERVER_PASSWORD") or values.get("SERVER_PASSWORD")
    else:
        raise RuntimeError(f"Unbekannte SSH-role={role!r} (web|auto|voice|old)")
    if not host or not password:
        raise RuntimeError(f"Host/Passwort für role={role} fehlt in {SECRETS_FILE.name}")
    return {"SERVER_HOST": host, "SERVER_USER": user, "SERVER_PASSWORD": password}


def ssh_connect(client, timeout=20, banner_timeout=20, role: str = "web"):
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

"""Pro-Kunde n8n-Workflows erzeugen und auf dem Server importieren."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kunden_ids import n8n_order_webhook, n8n_slug, validate_kunde_id

ROOT = Path(__file__).resolve().parent
KUNDEN_DIR = ROOT / "kunden"
TEMPLATE_DIR = ROOT / "infra" / "n8n" / "kunde"
N8N_ENV = "/opt/n8n/.env"
REMOTE_IMPORT_BASE = "/tmp/n8n-kunde"

HANDWERK_BRANCHEN = frozenset({"handwerk", "maler", "dach", "elektro"})


def _load_kunde_json(kid: str) -> tuple[dict, Path]:
    kid = kid.upper()
    for p in sorted(KUNDEN_DIR.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        if (data.get("id") or "").upper() == kid:
            return data, p
    raise FileNotFoundError(f"Kunde {kid} nicht in kunden/")


def _sms_sender(kunde: dict) -> str:
    name = (kunde.get("name") or "Kunde")[:11]
    return re.sub(r"[^A-Za-z0-9]", "", name)[:11] or "Webschmiede"


def _owner_phone(kunde: dict) -> str:
    n8n = kunde.get("n8n") or {}
    if n8n.get("owner_phone"):
        return str(n8n["owner_phone"]).strip()
    tel = (kunde.get("kontakt") or {}).get("telefon", "")
    return str(tel).strip()


def _alert_email(kunde: dict) -> str:
    n8n = kunde.get("n8n") or {}
    if n8n.get("alert_email"):
        return str(n8n["alert_email"]).strip()
    return (kunde.get("kontakt") or {}).get("email", "").strip()


def _bookkeeper_email(kunde: dict) -> str:
    return ((kunde.get("buchhaltung") or {}).get("bookkeeper_email") or "").strip()


def _anfrage_webhook(kid: str, base: str = "http://127.0.0.1:5678") -> str:
    return f"{base.rstrip('/')}/webhook/new-anfrage-{n8n_slug(kid)}"


def templates_for_kunde(kunde: dict) -> list[str]:
    branche = (kunde.get("branche") or "").strip().lower()
    if branche in HANDWERK_BRANCHEN:
        names = ["anfrage-alert.json", "buchhaltung-monat.json"]
    else:
        names = ["order-alert.json", "buchhaltung-monat.json"]
    return names


def render_template(template_name: str, kunde: dict) -> dict:
    kid = kunde["id"].upper()
    slug = n8n_slug(kid)
    raw = (TEMPLATE_DIR / template_name).read_text(encoding="utf-8")
    bookkeeper = _bookkeeper_email(kunde)
    if template_name == "buchhaltung-monat.json" and not bookkeeper:
        bookkeeper = _alert_email(kunde) or "bitte-buchhaltung@kunde.de"

    text = (
        raw.replace("__KUNDE_ID__", kid)
        .replace("__KUNDE_SLUG__", slug)
        .replace("__KUNDE_NAME__", (kunde.get("name") or kid).replace('"', "'"))
        .replace("__OWNER_PHONE__", _owner_phone(kunde) or "+4900000000000")
        .replace("__ALERT_EMAIL__", _alert_email(kunde) or "inhaber@kunde.de")
        .replace("__BOOKKEEPER_EMAIL__", bookkeeper)
        .replace("__SMS_SENDER__", _sms_sender(kunde))
    )
    wf = json.loads(text)
    wf["active"] = False
    return wf


def build_kunde_workflows(kunde: dict) -> list[dict]:
    return [render_template(name, kunde) for name in templates_for_kunde(kunde)]


def kunde_n8n_config(kunde: dict, workflow_names: list[str]) -> dict[str, Any]:
    kid = kunde["id"].upper()
    branche = (kunde.get("branche") or "").strip().lower()
    cfg: dict[str, Any] = {
        "provisioned_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "workflows": workflow_names,
        "owner_phone": _owner_phone(kunde),
        "alert_email": _alert_email(kunde),
    }
    if branche in HANDWERK_BRANCHEN:
        cfg["anfrage_webhook"] = _anfrage_webhook(kid)
        cfg["portal_mode"] = "handwerk"
    else:
        cfg["order_webhook"] = n8n_order_webhook(kid)
        cfg["portal_mode"] = "gastro"
    return cfg


def n8n_env_lines_for_kunde(kunde: dict) -> dict[str, str]:
    """Optionale kundenspezifische n8n-Env-Variablen (Prefix = Kunden-ID)."""
    kid = kunde["id"].upper()
    lines: dict[str, str] = {}
    phone = _owner_phone(kunde)
    if phone:
        lines[f"{kid}_OWNER_PHONE"] = phone
    bk = _bookkeeper_email(kunde)
    if bk:
        lines[f"{kid}_BOOKKEEPER_EMAIL"] = bk
    n8n = kunde.get("n8n") or {}
    if n8n.get("seven_api_key"):
        lines[f"{kid}_SEVEN_API_KEY"] = str(n8n["seven_api_key"]).strip()
    if n8n.get("admin_password"):
        lines[f"{kid}_ADMIN_PASSWORD"] = str(n8n["admin_password"]).strip()
    return lines


def update_kunde_json(kid: str, n8n_cfg: dict[str, Any]) -> dict:
    kunde, path = _load_kunde_json(kid)
    kunde["n8n"] = {**(kunde.get("n8n") or {}), **n8n_cfg}
    path.write_text(json.dumps(kunde, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return kunde


def provision_kunde(kid: str) -> dict[str, Any]:
    """Einstieg: lokal (SSH zum Server) oder direkt auf dem Server."""
    if Path("/opt/n8n/.env").exists():
        return _provision_on_server(kid)
    return provision_via_ssh(kid)


def _provision_on_server(kid: str) -> dict[str, Any]:
    import subprocess

    if not validate_kunde_id(kid):
        raise ValueError(f"Ungueltige Kunden-ID: {kid}")

    kunde, _ = _load_kunde_json(kid)
    workflows = build_kunde_workflows(kunde)
    names = [w["name"] for w in workflows]
    remote_dir = Path(f"/tmp/n8n-kunde-{kid.upper()}")
    remote_dir.mkdir(parents=True, exist_ok=True)
    for i, wf in enumerate(workflows):
        (remote_dir / f"wf-{i}.json").write_text(
            json.dumps(wf, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    import sqlite3

    db = "/opt/n8n/data/.n8n/database.sqlite"
    conn = sqlite3.connect(db)
    for wid, name in conn.execute(
        "SELECT id, name FROM workflow_entity WHERE name LIKE ?", (kid.upper() + " %",)
    ).fetchall():
        conn.execute("DELETE FROM workflow_entity WHERE id=?", (wid,))
        print("removed:", name)
    conn.commit()
    conn.close()

    env_path = Path(N8N_ENV)
    env_text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    lines = [ln for ln in env_text.splitlines() if ln.strip()]
    keys = set(n8n_env_lines_for_kunde(kunde).keys())
    lines = [ln for ln in lines if not any(ln.startswith(f"{k}=") for k in keys)]
    for key, val in n8n_env_lines_for_kunde(kunde).items():
        lines.append(f"{key}={val}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    subprocess.run(
        f"export $(grep -v '^#' {N8N_ENV} | xargs) && "
        f"N8N_USER_FOLDER=/opt/n8n/data "
        f"n8n import:workflow --separate --input={remote_dir}",
        shell=True,
        check=False,
        timeout=180,
    )

    conn = sqlite3.connect(db)
    for wid, name, active in conn.execute(
        "SELECT id, name, active FROM workflow_entity WHERE name LIKE ?",
        (kid.upper() + " %",),
    ).fetchall():
        if not active:
            conn.execute("UPDATE workflow_entity SET active=1 WHERE id=?", (wid,))
            print("activated:", name)
    conn.commit()
    conn.close()

    n8n_cfg = kunde_n8n_config(kunde, names)
    kunde = update_kunde_json(kid, n8n_cfg)
    return {"ok": True, "kunde_id": kid.upper(), "workflows": names, "n8n": kunde.get("n8n")}


def provision_via_ssh(kid: str) -> dict[str, Any]:
    import paramiko
    from agency_config import ssh_connect

    if not validate_kunde_id(kid):
        raise ValueError(f"Ungueltige Kunden-ID: {kid}")

    kunde, _ = _load_kunde_json(kid)
    workflows = build_kunde_workflows(kunde)
    names = [w["name"] for w in workflows]
    remote_dir = f"{REMOTE_IMPORT_BASE}-{kid.upper()}"

    client = paramiko.SSHClient()
    ssh_connect(client)

    def run(cmd: str, timeout: int = 120) -> str:
        _, o, e = client.exec_command(cmd, timeout=timeout)
        return (o.read() + e.read()).decode("utf-8", errors="replace").strip()

    run(f"rm -rf {remote_dir} && mkdir -p {remote_dir}")
    sftp = client.open_sftp()
    for i, wf in enumerate(workflows):
        fname = f"wf-{i}.json"
        with sftp.open(f"{remote_dir}/{fname}", "w") as f:
            f.write(json.dumps(wf, ensure_ascii=False, indent=2))
    sftp.close()

    # Alte Workflows dieses Kunden entfernen
    py_del = f"""
import sqlite3
kid = {kid.upper()!r}
db = '/opt/n8n/data/.n8n/database.sqlite'
conn = sqlite3.connect(db)
cur = conn.execute("SELECT id, name FROM workflow_entity WHERE name LIKE ?", (kid + ' %',))
rows = cur.fetchall()
for wid, name in rows:
    conn.execute('DELETE FROM workflow_entity WHERE id=?', (wid,))
    print('removed:', name)
conn.commit()
conn.close()
"""
    sftp = client.open_sftp()
    with sftp.open("/tmp/n8n_kunde_del.py", "w") as f:
        f.write(py_del)
    sftp.close()
    print(run("/root/app/venv/bin/python /tmp/n8n_kunde_del.py"))

    # Kunden-Env in n8n
    for key, val in n8n_env_lines_for_kunde(kunde).items():
        safe = str(val).replace("'", "'\"'\"'")
        run(
            f"grep -q '^{key}=' {N8N_ENV} 2>/dev/null && "
            f"sed -i 's|^{key}=.*|{key}={safe}|' {N8N_ENV} || "
            f"echo '{key}={safe}' >> {N8N_ENV}"
        )

    out = run(
        f"export $(grep -v '^#' {N8N_ENV} | xargs) && "
        f"N8N_USER_FOLDER=/opt/n8n/data "
        f"n8n import:workflow --separate --input={remote_dir} 2>&1",
        timeout=180,
    )
    print(out)

    # Nur neue Kunden-Workflows aktivieren
    py_act = f"""
import sqlite3
kid = {kid.upper()!r}
db = '/opt/n8n/data/.n8n/database.sqlite'
conn = sqlite3.connect(db)
rows = conn.execute("SELECT id, name, active FROM workflow_entity WHERE name LIKE ?", (kid + ' %',)).fetchall()
for wid, name, active in rows:
    if not active:
        conn.execute('UPDATE workflow_entity SET active=1 WHERE id=?', (wid,))
        print('activated:', name)
conn.commit()
conn.close()
print('kunde workflows:', len(rows))
"""
    sftp = client.open_sftp()
    with sftp.open("/tmp/n8n_kunde_act.py", "w") as f:
        f.write(py_act)
    sftp.close()
    print(run("/root/app/venv/bin/python /tmp/n8n_kunde_act.py"))
    run("systemctl restart n8n")

    client.close()

    n8n_cfg = kunde_n8n_config(kunde, names)
    kunde = update_kunde_json(kid, n8n_cfg)
    return {"ok": True, "kunde_id": kid, "workflows": names, "n8n": kunde.get("n8n")}

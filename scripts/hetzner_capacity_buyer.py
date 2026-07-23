#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hetzner Capacity Buyer — wartet auf DE-Kapazität und bestellt.

Ziel (einmalig, bis erledigt):
  2× cx43 + 1× cx53 in Deutschland (bevorzugt fsn1, sonst nbg1)

State + Root-Passwörter: STATE_PATH (nicht committen).
Cron: alle 5 Minuten auf auto-01.

Env / Secrets:
  HETZNER_API_TOKEN  (Pflicht)
  Optional SMTP aus deploy.secrets.local für Erfolgs-Mail
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

API = "https://api.hetzner.cloud/v1"
IMAGE = "ubuntu-24.04"
# Nur Deutschland. Reihenfolge = Priorität.
LOCATIONS = ["fsn1", "nbg1"]

# Was wir noch brauchen (nicht bestehende Server zählen).
TARGETS = [
    {"slot": "cx43-1", "server_type": "cx43", "name": "cx43-de-1"},
    {"slot": "cx43-2", "server_type": "cx43", "name": "cx43-de-2"},
    {"slot": "cx53-1", "server_type": "cx53", "name": "cx53-de-1"},
]

DEFAULT_STATE = Path("/var/lib/webschmiede/hetzner-buyer-state.json")
LOCAL_STATE = ROOT / "agency" / "hetzner-buyer-state.local.json"
SECRETS_CANDIDATES = [
    Path("/root/app/deploy.secrets.local"),
    ROOT / "deploy.secrets.local",
]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_secrets() -> dict[str, str]:
    out: dict[str, str] = {}
    for p in SECRETS_CANDIDATES:
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            out[k.strip()] = v.strip()
    # env overrides
    for k in ("HETZNER_API_TOKEN", "AGENCY_OWNER_EMAIL", "AGENCY_SMTP_HOST",
              "AGENCY_SMTP_USER", "AGENCY_SMTP_PASS", "AGENCY_SMTP_PORT", "AGENCY_SMTP_FROM"):
        if os.environ.get(k):
            out[k] = os.environ[k].strip()
    return out


def state_path() -> Path:
    env = os.environ.get("HETZNER_BUYER_STATE", "").strip()
    if env:
        return Path(env)
    try:
        if os.name != "nt" and hasattr(os, "geteuid") and os.geteuid() == 0:
            DEFAULT_STATE.parent.mkdir(parents=True, exist_ok=True)
            return DEFAULT_STATE
    except OSError:
        pass
    if DEFAULT_STATE.parent.exists():
        try:
            return DEFAULT_STATE
        except OSError:
            pass
    LOCAL_STATE.parent.mkdir(parents=True, exist_ok=True)
    return LOCAL_STATE


def load_state(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "created": [],
        "done": False,
        "last_check": None,
        "last_error": None,
        "attempts": 0,
    }


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def api(token: str, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "webschmiede-hetzner-buyer/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"error": {"message": raw[:300]}}
        return e.code, payload


def type_available_in_location(token: str, server_type: str, location: str) -> bool:
    """True wenn Create realistisch möglich (Datacenter available-Liste)."""
    code, data = api(token, "GET", "/datacenters")
    if code >= 400:
        return False
    for dc in data.get("datacenters") or []:
        loc = ((dc.get("location") or {}).get("name") or "")
        if loc != location:
            continue
        st = dc.get("server_types") or {}
        available = st.get("available") or []
        # API liefert IDs oder Namen je nach Version — beides prüfen
        names_or_ids = set(str(x) for x in available)
        if server_type in names_or_ids:
            return True
        # Fallback: Typ-ID nachschlagen
        code2, types = api(token, "GET", "/server_types")
        if code2 < 400:
            for t in types.get("server_types") or []:
                if t.get("name") == server_type and str(t.get("id")) in names_or_ids:
                    return True
    return False


def create_server(token: str, *, name: str, server_type: str, location: str) -> tuple[bool, dict]:
    body = {
        "name": name,
        "server_type": server_type,
        "image": IMAGE,
        "location": location,
        "start_after_create": True,
        "labels": {
            "managed_by": "webschmiede-buyer",
            "role": server_type,
        },
    }
    code, data = api(token, "POST", "/servers", body)
    if code in (200, 201) and data.get("server"):
        return True, data
    err = (data.get("error") or {})
    return False, {
        "http": code,
        "code": err.get("code"),
        "message": err.get("message") or json.dumps(data)[:300],
    }


def send_mail(secrets: dict, subject: str, body: str) -> None:
    to = secrets.get("AGENCY_OWNER_EMAIL") or secrets.get("AGENCY_MAIL_BCC") or ""
    host = secrets.get("AGENCY_SMTP_HOST")
    user = secrets.get("AGENCY_SMTP_USER")
    password = secrets.get("AGENCY_SMTP_PASS")
    if not (to and host and user and password):
        print("MAIL_SKIP: SMTP/Owner nicht konfiguriert")
        return
    import smtplib
    from email.mime.text import MIMEText

    port = int(secrets.get("AGENCY_SMTP_PORT") or "587")
    frm = secrets.get("AGENCY_SMTP_FROM") or user
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = frm
    msg["To"] = to
    with smtplib.SMTP(host, port, timeout=30) as s:
        s.ehlo()
        s.starttls()
        s.ehlo()
        s.login(user, password)
        s.sendmail(user, [to], msg.as_string())
    print(f"MAIL_OK -> {to}")


def pending_slots(state: dict) -> list[dict]:
    done_slots = {c.get("slot") for c in state.get("created") or []}
    return [t for t in TARGETS if t["slot"] not in done_slots]


def run(*, dry_run: bool = False, force_try: bool = False) -> int:
    secrets = load_secrets()
    token = secrets.get("HETZNER_API_TOKEN", "")
    if not token:
        print("ERROR: HETZNER_API_TOKEN fehlt")
        return 2

    path = state_path()
    state = load_state(path)
    state["attempts"] = int(state.get("attempts") or 0) + 1
    state["last_check"] = _now()

    pending = pending_slots(state)
    if not pending:
        state["done"] = True
        save_state(path, state)
        print("DONE: alle Ziel-Server bereits bestellt")
        return 0

    print(f"pending={ [p['slot']+':'+p['server_type'] for p in pending] } locations={LOCATIONS}")

    # Availability overview
    for loc in LOCATIONS:
        for typ in sorted({p["server_type"] for p in pending}):
            ok = type_available_in_location(token, typ, loc)
            print(f"  avail {typ}@{loc}={ok}")

    if dry_run:
        save_state(path, state)
        print("DRY_RUN: keine Bestellung")
        return 0

    bought_this_run = []
    last_err = None

    for target in pending:
        bought = False
        for loc in LOCATIONS:
            # Schnellcheck; bei force_try trotzdem POST (Hetzner ist Quelle der Wahrheit)
            if not force_try and not type_available_in_location(token, target["server_type"], loc):
                continue
            # eindeutiger Name falls schon vergeben
            name = target["name"]
            if loc != "fsn1":
                name = f"{target['name']}-{loc}"
            print(f"TRY create {name} {target['server_type']} @{loc}")
            ok, result = create_server(
                token,
                name=name,
                server_type=target["server_type"],
                location=loc,
            )
            if ok:
                server = result.get("server") or {}
                root_pw = result.get("root_password") or ""
                ipv4 = ((server.get("public_net") or {}).get("ipv4") or {})
                ip = ipv4.get("ip") if isinstance(ipv4, dict) else None
                entry = {
                    "slot": target["slot"],
                    "name": server.get("name") or name,
                    "id": server.get("id"),
                    "server_type": target["server_type"],
                    "location": loc,
                    "ip": ip,
                    "root_password": root_pw,
                    "created_at": _now(),
                }
                state.setdefault("created", []).append(entry)
                bought_this_run.append(entry)
                bought = True
                print(f"CREATED id={entry['id']} name={entry['name']} ip={ip}")
                break
            last_err = result
            code = result.get("code") or ""
            print(f"  FAIL {result.get('http')} {code}: {result.get('message')}")
            if code not in ("resource_unavailable", "server_type_unavailable", ""):
                # Name conflict → retry with suffix
                if code == "uniqueness_error" or "unique" in str(result.get("message", "")).lower():
                    name = f"{target['name']}-{int(time.time()) % 10000}"
                    ok2, result2 = create_server(
                        token,
                        name=name,
                        server_type=target["server_type"],
                        location=loc,
                    )
                    if ok2:
                        server = result2.get("server") or {}
                        ipv4 = ((server.get("public_net") or {}).get("ipv4") or {})
                        entry = {
                            "slot": target["slot"],
                            "name": server.get("name") or name,
                            "id": server.get("id"),
                            "server_type": target["server_type"],
                            "location": loc,
                            "ip": ipv4.get("ip") if isinstance(ipv4, dict) else None,
                            "root_password": result2.get("root_password") or "",
                            "created_at": _now(),
                        }
                        state.setdefault("created", []).append(entry)
                        bought_this_run.append(entry)
                        bought = True
                        print(f"CREATED id={entry['id']} name={entry['name']}")
                        break
                # other hard errors: stop trying this type at this loc
                continue
        if not bought:
            print(f"SKIP {target['slot']}: noch keine Kapazität")

    state["last_error"] = last_err
    if not pending_slots(state):
        state["done"] = True
    save_state(path, state)

    if bought_this_run:
        lines = [
            "Hetzner Buyer: neue Server bestellt",
            "",
        ]
        for e in bought_this_run:
            lines.append(
                f"- {e['name']} ({e['server_type']}) @{e['location']} "
                f"IP={e.get('ip') or '?'} id={e.get('id')}"
            )
            if e.get("root_password"):
                lines.append(f"  root-Passwort: {e['root_password']}")
        lines += [
            "",
            f"State: {path}",
            "Noch offen: " + (", ".join(p["slot"] for p in pending_slots(state)) or "nichts"),
            "",
            "Passwort auch in der Hetzner Console zurücksetzbar.",
        ]
        try:
            send_mail(secrets, "[Webschmiede] Hetzner Server bestellt", "\n".join(lines))
        except Exception as exc:
            print(f"MAIL_FAIL: {exc}")
        return 0

    print("NO_BUY: Kapazität noch nicht da")
    return 0


def main() -> int:
    args = set(sys.argv[1:])
    dry = "--dry-run" in args or "-n" in args
    force = "--force-try" in args
    status = "--status" in args
    if status:
        path = state_path()
        state = load_state(path)
        print(json.dumps({
            "state_path": str(path),
            "done": state.get("done"),
            "created": [
                {k: v for k, v in c.items() if k != "root_password"}
                for c in (state.get("created") or [])
            ],
            "pending": [p["slot"] for p in pending_slots(state)],
            "last_check": state.get("last_check"),
            "attempts": state.get("attempts"),
        }, indent=2, ensure_ascii=False))
        return 0
    return run(dry_run=dry, force_try=force)


if __name__ == "__main__":
    raise SystemExit(main())

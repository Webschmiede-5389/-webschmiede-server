#!/usr/bin/env python3
"""Dual CX43 Watch: web + auto Health, optional Mail bei Alarm."""
from __future__ import annotations

import argparse
import json
import smtplib
import sys
from email.mime.text import MIMEText
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app" / "backend"))

import dual_infra as dual  # noqa: E402


def _secrets() -> dict[str, str]:
    out: dict[str, str] = {}
    path = ROOT / "deploy.secrets.local"
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _mail(subject: str, body: str, sec: dict[str, str]) -> dict:
    to = sec.get("AGENCY_OWNER_EMAIL") or sec.get("AGENCY_SMTP_USER") or ""
    host = sec.get("AGENCY_SMTP_HOST") or sec.get("SMTP_HOST") or ""
    user = sec.get("AGENCY_SMTP_USER") or sec.get("SMTP_USER") or ""
    password = (
        sec.get("AGENCY_SMTP_PASSWORD")
        or sec.get("AGENCY_SMTP_PASS")
        or sec.get("SMTP_PASSWORD")
        or ""
    )
    port = int(sec.get("AGENCY_SMTP_PORT") or sec.get("SMTP_PORT") or 587)
    if not (to and host and user and password):
        return {"ok": False, "error": "SMTP fehlt"}
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to
    with smtplib.SMTP(host, port, timeout=30) as s:
        s.starttls()
        s.login(user, password)
        s.sendmail(user, [to], msg.as_string())
    return {"ok": True, "to": to}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--mail-on-alert", action="store_true")
    ap.add_argument("--mail-always", action="store_true")
    args = ap.parse_args()
    data = dual.dual_status()
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        sys.stdout.buffer.write((dual.markdown_status(data) + "\n").encode("utf-8", errors="replace"))
    if args.mail_always or (args.mail_on_alert and not data.get("ok")):
        sec = _secrets()
        sub = "[Dual-CX43] OK" if data.get("ok") else "[Dual-CX43] ALARM"
        print(_mail(sub, dual.markdown_status(data), sec))
    return 0 if data.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

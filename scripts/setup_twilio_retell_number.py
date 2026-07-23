#!/usr/bin/env python3
"""Prüft Twilio-Secrets und listet Status. SIP+Retell-Import folgt, wenn Nummer da ist.

Kein Nummernkauf hier (Kostet Geld, braucht Regulatory Bundle in Twilio Console).
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def secrets() -> dict[str, str]:
    out: dict[str, str] = {}
    for path in (ROOT / "deploy.secrets.local", Path("/root/app/deploy.secrets.local")):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            out.setdefault(k.strip(), v.strip())
    return out


def twilio_get(sid: str, token: str, path: str) -> dict | list:
    import base64

    auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
    req = urllib.request.Request(
        f"https://api.twilio.com/2010-04-01{path}",
        headers={"Authorization": f"Basic {auth}"},
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read().decode("utf-8", "replace") or "{}")


def main() -> int:
    sec = secrets()
    sid = (sec.get("TWILIO_ACCOUNT_SID") or "").strip()
    token = (sec.get("TWILIO_AUTH_TOKEN") or "").strip()
    number = (sec.get("TWILIO_VOICE_NUMBER") or "").strip()

    print("Twilio Setup-Check")
    print("  ACCOUNT_SID:", "ja" if sid.startswith("AC") else "fehlt")
    print("  AUTH_TOKEN:", "ja" if len(token) > 10 else "fehlt")
    print("  VOICE_NUMBER:", number or "fehlt")
    print("  SIP_TERMINATION:", (sec.get("TWILIO_SIP_TERMINATION_URI") or "fehlt"))

    if not (sid.startswith("AC") and token):
        print("\nNächster Schritt: Twilio-Account anlegen, Keys in deploy.secrets.local")
        print("oder /agency-setup speichern. Doku: docs/agency/twilio-retell-setup.md")
        return 1

    try:
        acc = twilio_get(sid, token, f"/Accounts/{sid}.json")
        print("\nAccount OK:", acc.get("friendly_name"), "status=", acc.get("status"))
        nums = twilio_get(sid, token, f"/Accounts/{sid}/IncomingPhoneNumbers.json?PageSize=20")
        items = nums.get("incoming_phone_numbers") if isinstance(nums, dict) else []
        print(f"Nummern im Account: {len(items or [])}")
        for n in items or []:
            print(" -", n.get("phone_number"), n.get("friendly_name") or "")
    except urllib.error.HTTPError as e:
        print("Twilio API Fehler:", e.code, e.read().decode("utf-8", "replace")[:300])
        return 1
    except Exception as e:
        print("Fehler:", e)
        return 1

    if not number:
        print("\nNächster Schritt: DE-Regulatory Bundle freigeben, dann Ortsnummer kaufen.")
        return 0

    print("\nWenn SIP-Trunk steht: Nummer in Retell importieren (siehe Doku).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

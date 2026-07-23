#!/usr/bin/env python3
"""Agency Router CLI – Intent klassifizieren (lokal oder Live-API)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Webschmiede AI-Router")
    ap.add_argument("message", nargs="?", help="Auftragstext")
    ap.add_argument("--file", "-f", help="Text aus Datei")
    ap.add_argument("--live", action="store_true", help="POST an Live-API statt lokal")
    ap.add_argument("--playbook", action="store_true", help="Cursor-Playbook ausgeben")
    args = ap.parse_args()

    msg = (args.message or "").strip()
    if args.file:
        msg = Path(args.file).read_text(encoding="utf-8").strip()
    if not msg:
        print("message fehlt", file=sys.stderr)
        return 2

    if args.live:
        import urllib.request

        # Secrets lokal: deploy.secrets.local oder Env
        secret = os.getenv("CRON_SECRET", "").strip()
        agency_pw = os.getenv("AGENCY_ADMIN_PASSWORD", "").strip()
        if not secret and not agency_pw:
            secrets = ROOT / "deploy.secrets.local"
            if secrets.exists():
                for line in secrets.read_text(encoding="utf-8", errors="replace").splitlines():
                    if line.startswith("CRON_SECRET=") and not secret:
                        secret = line.split("=", 1)[1].strip().strip('"')
                    if line.startswith("AGENCY_ADMIN_PASSWORD=") and not agency_pw:
                        agency_pw = line.split("=", 1)[1].strip().strip('"')
        headers = {"Content-Type": "application/json"}
        if secret:
            headers["X-Cron-Secret"] = secret
        elif agency_pw:
            headers["X-Agency-Password"] = agency_pw
        else:
            print("Kein CRON_SECRET / AGENCY_ADMIN_PASSWORD", file=sys.stderr)
            return 1
        req = urllib.request.Request(
            "https://digitalehandwerkskunst.de/api/agency/router",
            data=json.dumps({"message": msg}).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    else:
        import agency_router as router

        result = router.classify(msg, source="cli")
        result["playbook"] = router.cursor_playbook(result)

    if args.playbook:
        print(result.get("playbook") or "")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

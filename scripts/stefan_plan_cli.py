#!/usr/bin/env python3
"""Stefan: Schlachtplan oder Guru-Filter."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))


def _auth_headers() -> dict[str, str]:
    secret = os.getenv("CRON_SECRET", "").strip()
    pw = os.getenv("AGENCY_ADMIN_PASSWORD", "").strip()
    secrets = ROOT / "deploy.secrets.local"
    if secrets.exists():
        for line in secrets.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("CRON_SECRET=") and not secret:
                secret = line.split("=", 1)[1].strip().strip('"')
            if line.startswith("AGENCY_ADMIN_PASSWORD=") and not pw:
                pw = line.split("=", 1)[1].strip().strip('"')
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-Cron-Secret"] = secret
    elif pw:
        headers["X-Agency-Password"] = pw
    return headers


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("brief", nargs="?", help="Idee oder Projektbriefing")
    ap.add_argument("--firma", default="")
    ap.add_argument("--filter", action="store_true", help="Nur Guru-/Reality-Filter")
    ap.add_argument("--growth", action="store_true", help="Wachstums-/Funnel-Plan")
    ap.add_argument("--niche", default="")
    ap.add_argument("--ticket", default="5000")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    brief = (args.brief or "").strip()
    if not brief and not args.growth:
        print("brief fehlt", file=sys.stderr)
        return 2
    if args.growth and not brief:
        brief = "B2B High-Ticket Portal Automation"

    if args.live:
        headers = _auth_headers()
        if len(headers) < 2:
            print("Kein CRON_SECRET / AGENCY_ADMIN_PASSWORD", file=sys.stderr)
            return 1
        if args.filter:
            url = "https://digitalehandwerkskunst.de/api/agency/stefan/filter"
            payload = {"idea": brief}
        elif args.growth:
            url = "https://digitalehandwerkskunst.de/api/agency/stefan/growth"
            payload = {"brief": brief, "niche": args.niche, "ticket": args.ticket}
        else:
            url = "https://digitalehandwerkskunst.de/api/agency/stefan/plan"
            payload = {"brief": brief, "firma": args.firma}
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    else:
        import agency_stefan as stefan

        if args.filter:
            data = stefan.filter_idea(brief)
        elif args.growth:
            data = stefan.growth_plan(brief, niche=args.niche, ticket=args.ticket)
        else:
            data = stefan.plan_project(brief, firma=args.firma)

    out = json.dumps(data, ensure_ascii=False, indent=2) if args.json else (data.get("markdown") or str(data))
    sys.stdout.buffer.write((out + "\n").encode("utf-8", errors="replace"))
    return 0 if data.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

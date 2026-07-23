#!/usr/bin/env python3
"""Commander: Fulfillment-Pack, Kapazitaet, Tagesbriefing."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

import agency_commander as cmd  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("brief", nargs="?", default="")
    ap.add_argument("--firma", default="")
    ap.add_argument("--budget", default="5000")
    ap.add_argument("--fulfillment", action="store_true")
    ap.add_argument("--capacity", action="store_true")
    ap.add_argument("--briefing", action="store_true")
    ap.add_argument("--ticket", type=float, default=5000)
    ap.add_argument("--target", type=float, default=30000)
    ap.add_argument("--hours-week", type=float, default=10)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.capacity:
        data = cmd.capacity_plan(
            ticket=args.ticket, target_month=args.target, hours_week_sales=args.hours_week
        )
    elif args.briefing:
        data = cmd.daily_briefing(ticket=str(int(args.ticket)))
    elif args.fulfillment or args.firma or args.brief:
        data = cmd.fulfillment_pack(
            firma=args.firma or "Neuer B2B-Kunde",
            brief=args.brief or f"B2B Portal/Automation ca. {args.budget} EUR",
            budget=args.budget,
        )
    else:
        print("Nutze --fulfillment, --capacity oder --briefing", file=sys.stderr)
        return 2

    out = json.dumps(data, ensure_ascii=False, indent=2) if args.json else (data.get("markdown") or str(data))
    sys.stdout.buffer.write((out + "\n").encode("utf-8", errors="replace"))
    return 0 if data.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Radar CLI: Scan / Status / Queue."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

import agency_radar as radar  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Webschmiede Radar / Trend-Scout")
    ap.add_argument("cmd", nargs="?", default="scan", choices=["scan", "status", "queue", "add", "approve", "reject"])
    ap.add_argument("--date", default="")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--name", default="")
    ap.add_argument("--reason", default="")
    ap.add_argument("--id", default="")
    args = ap.parse_args()

    if args.cmd == "status":
        data = radar.status()
    elif args.cmd == "queue":
        data = radar.load_queue()
    elif args.cmd == "add":
        data = radar.queue_install(args.name, reason=args.reason)
    elif args.cmd == "approve":
        data = radar.approve_install(args.id, approve=True)
    elif args.cmd == "reject":
        data = radar.approve_install(args.id, approve=False)
    else:
        data = radar.build_report(live=not args.offline, day=args.date or None)

    if args.json:
        slim = {k: v for k, v in data.items() if k != "markdown"}
        print(json.dumps(slim, ensure_ascii=False, indent=2)[:12000])
    else:
        if data.get("markdown"):
            sys.stdout.buffer.write((data["markdown"] + "\n").encode("utf-8", errors="replace"))
        elif data.get("path"):
            print("wrote", data["path"])
        else:
            print(json.dumps(data, ensure_ascii=False, indent=2)[:4000])
    return 0 if data.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())

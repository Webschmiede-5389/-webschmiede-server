#!/usr/bin/env python3
"""Scout WF3: Kampagne / Queue (kein Auto-Send)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

import agency_scout as scout  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vertical", default="")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--ticket", default="5000")
    ap.add_argument("--queue", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.queue:
        data = scout.queue_summary(limit=args.limit)
    else:
        data = scout.campaign(vertical=args.vertical, limit=args.limit, ticket=args.ticket)
    out = json.dumps(data, ensure_ascii=False, indent=2) if args.json else (data.get("markdown") or str(data))
    sys.stdout.buffer.write((out + "\n").encode("utf-8", errors="replace"))
    return 0 if data.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

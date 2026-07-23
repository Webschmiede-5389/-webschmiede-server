#!/usr/bin/env python3
"""Agency-Hirn CLI: Nachricht → Router + Dispatch."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

import agency_brain as brain  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("message", nargs="?", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-dispatch", action="store_true")
    ap.add_argument("--commander", action="store_true")
    ap.add_argument("--force", default="")
    args = ap.parse_args()
    msg = args.message.strip()
    if not msg and not sys.stdin.isatty():
        msg = sys.stdin.read().strip()
    if not msg:
        print("Usage: python scripts/agency_brain_cli.py \"Nachricht…\"")
        return 2
    data = brain.process(
        msg,
        source="cli",
        force_agent=args.force or None,
        dispatch=not args.no_dispatch,
        include_commander=args.commander,
    )
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2)[:12000])
    else:
        sys.stdout.buffer.write((brain.markdown(data) + "\n").encode("utf-8", errors="replace"))
    return 0 if data.get("sharp") else 1


if __name__ == "__main__":
    raise SystemExit(main())

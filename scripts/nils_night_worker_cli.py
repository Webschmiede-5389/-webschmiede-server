#!/usr/bin/env python3
"""CLI: Nils Night-Worker / Hirn-Wächter."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

import nils_brain_watch as bw  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--night", action="store_true", help="Nacht-Digest immer an Christian")
    ap.add_argument("--no-notify", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    data = bw.run(notify=not args.no_notify, night=args.night)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, default=str)[:12000])
    else:
        print(data.get("text") or "")
    return 0 if data.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

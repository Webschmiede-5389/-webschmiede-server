#!/usr/bin/env python3
"""Ops-Guardian CLI."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

import ops_guardian as g  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="run", choices=["run", "status"])
    ap.add_argument("--no-repair", action="store_true")
    ap.add_argument("--mail", action="store_true")
    ap.add_argument("--force-mail", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.cmd == "status":
        data = g.status()
    else:
        data = g.run(repair=not args.no_repair, mail=args.mail, force_mail=args.force_mail)
    if args.json:
        print(json.dumps({k: v for k, v in data.items() if k != "markdown"}, ensure_ascii=False, indent=2)[:12000])
    else:
        sys.stdout.buffer.write(((data.get("markdown") or json.dumps(data, indent=2)) + "\n").encode("utf-8", errors="replace"))
    return 0 if data.get("ok", True) or data.get("status") == "yellow" else 1


if __name__ == "__main__":
    raise SystemExit(main())

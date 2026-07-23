#!/usr/bin/env python3
"""Freigabe-Check CLI: Links/Dashboards prüfen bevor sie an Christian gehen."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

import agency_shipcheck as sc  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("text", nargs="*", help="URL(s) oder Text mit Links")
    ap.add_argument("--dashboard", default="", help="Kurzname: agency-setup, b2b, health, yassine…")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.dashboard:
        data = sc.check_dashboard(args.dashboard)
    else:
        blob = " ".join(args.text).strip()
        if not blob and not sys.stdin.isatty():
            blob = sys.stdin.read().strip()
        if not blob:
            print('Usage: python scripts/shipcheck_cli.py "https://…"')
            return 2
        data = sc.check_text(blob)
    if args.json:
        print(json.dumps({k: v for k, v in data.items() if k != "markdown"}, ensure_ascii=False, indent=2))
    else:
        sys.stdout.buffer.write(((data.get("markdown") or json.dumps(data, indent=2)) + "\n").encode("utf-8", errors="replace"))
    return 0 if data.get("ship") else 1


if __name__ == "__main__":
    raise SystemExit(main())

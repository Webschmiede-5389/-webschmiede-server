#!/usr/bin/env python3
"""CLI: Nils Tagesreport senden."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

import nils_daily_report as report  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-mail", action="store_true")
    ap.add_argument("--no-telegram", action="store_true")
    ap.add_argument("--print-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.print_only:
        data = report.build_report()
        print(data.get("text") or "")
        return 0
    data = report.send_report(mail=not args.no_mail, telegram=not args.no_telegram)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, default=str)[:8000])
    else:
        print((data.get("report") or {}).get("text") or "")
        print("telegram:", data.get("telegram"))
        print("mail:", data.get("mail"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

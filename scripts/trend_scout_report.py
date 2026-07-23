#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Trend-Scout / Radar: Wochenreport erzeugen (delegiert an agency_radar)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

import agency_radar as radar  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD", default="")
    ap.add_argument("--offline", action="store_true", help="ohne HTTP-Quellen")
    args = ap.parse_args()
    result = radar.build_report(live=not args.offline, day=args.date or None)
    print(f"wrote: {result.get('path')}")
    print(f"signals: {len(result.get('signals') or [])} pending_installs: {len(result.get('pending_installs') or [])}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

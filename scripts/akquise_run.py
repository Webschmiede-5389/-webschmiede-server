#!/usr/bin/env python3
"""
Webschmiede Akquise Engine — branchenunabhängig (Apify-ähnlich, self-hosted).

  python scripts/akquise_run.py --list
  python scripts/akquise_run.py --vertical gastro
  python scripts/akquise_run.py --vertical handwerk --radius 30
  python scripts/akquise_run.py --vertical gastro --no-crawl
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "akquise"))

from engine import list_verticals, run_pipeline, save_report  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Webschmiede Akquise Engine")
    parser.add_argument("--vertical", "-v", default="gastro", help="Vertical ID (akquise/verticals/)")
    parser.add_argument("--radius", type=float, default=0)
    parser.add_argument("--no-crawl", action="store_true")
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--list", action="store_true", help="Verfügbare Verticals")
    args = parser.parse_args()

    if args.list:
        print("Verticals:", ", ".join(list_verticals()))
        return 0

    print(f"Akquise Engine: vertical={args.vertical}")
    report = run_pipeline(
        args.vertical,
        radius_km=args.radius or None,
        no_crawl=args.no_crawl,
        workers=args.workers or None,
    )
    json_path, html_path, csv_path = save_report(report)
    print(f"\nReport: {html_path}")
    print(f"JSON:   {json_path}")
    print(f"CSV:    {csv_path}")
    print(f"HIGH: {report['high']} | MED: {report['medium']} | Total: {report['total']}")
    print(f"Anrufbereit: {report.get('call_ready', 0)} | Budget A: {report.get('budget_a', 0)}")
    for lead in report["leads"][:5]:
        intent = lead.get("intent") or {}
        print(f"  [{intent.get('budget_tier','?')}] {lead['name']} — {intent.get('label','')} | {intent.get('stack_summary','')[:60]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

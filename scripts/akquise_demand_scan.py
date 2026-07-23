#!/usr/bin/env python3
"""Reverse-Akquise Scan (Nachfrage: Website gesucht, Bestellportal, …)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "akquise"))

from demand import save_report, scan_demand  # noqa: E402


def main() -> int:
    print("Reverse-Akquise: Nachfrage-Scan …")
    report = scan_demand()
    jp, hp = save_report(report)
    print(f"Treffer: {report['total']}")
    print(f"JSON: {jp}")
    print(f"HTML: {hp}")
    print(f"Watch-Links: {len(report.get('watch_urls') or [])}")
    for h in (report.get("hits") or [])[:8]:
        print(f"  [{h['score']}] {h['intent_id']}: {h['title'][:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

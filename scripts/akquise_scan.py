#!/usr/bin/env python3
"""Legacy wrapper — nutzt Akquise Engine (gastro)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "akquise"))

from engine import run_pipeline, save_report  # noqa: E402

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--radius", type=float, default=0)
    p.add_argument("--no-crawl", action="store_true")
    p.add_argument("--workers", type=int, default=0)
    a = p.parse_args()
    r = run_pipeline("gastro", radius_km=a.radius or None, no_crawl=a.no_crawl, workers=a.workers or None)
    jp, hp, cp = save_report(r)
    print(f"Report: {hp}\nCSV: {cp}\nHIGH: {r['high']}")

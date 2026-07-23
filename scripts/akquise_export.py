#!/usr/bin/env python3
"""CSV-Export aus Akquise-Report (nur A+B, anrufbereit)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "akquise"))

from engine import export_csv, merge_config, save_report  # noqa: E402
from intent import derive_intent  # noqa: E402
from enrichment import score_from_signals  # noqa: E402


def main():
    p = argparse.ArgumentParser(description="Akquise Call-List CSV")
    p.add_argument("--report", "-r", help="Pfad zur JSON-Report-Datei")
    p.add_argument("--vertical", "-v", default="gastro")
    p.add_argument("--date", "-d", help="YYYY-MM-DD (default: neueste Datei)")
    p.add_argument("--tiers", default="AB", help="Budget-Tiers z.B. AB oder ABC")
    p.add_argument("--reprocess", action="store_true", help="Intent neu berechnen ohne Crawl")
    args = p.parse_args()

    if args.report:
        path = Path(args.report)
    else:
        rep_dir = ROOT / "docs" / "akquise" / "reports"
        if args.date:
            path = rep_dir / f"{args.date}-{args.vertical}.json"
        else:
            files = sorted(rep_dir.glob(f"*-{args.vertical}.json"), reverse=True)
            if not files:
                print("Kein Report gefunden")
                return 1
            path = files[0]

    report = json.loads(path.read_text(encoding="utf-8"))
    if args.reprocess:
        cfg = merge_config(report.get("vertical", args.vertical))
        for lead in report["leads"]:
            sig = lead.get("signals") or {}
            s, pr, angles = score_from_signals(lead, sig, cfg)
            lead["score"] = s
            lead["priority"] = pr
            lead["pitch_angles"] = angles
            lead["pitch_angle"] = angles[0] if angles else ""
            lead["intent"] = derive_intent(lead, sig, cfg)
        _, _, _ = save_report(report)
        print("Report neu berechnet.")
    csv_path = export_csv(report, tiers=args.tiers)
    n = sum(
        1 for l in report["leads"]
        if (l.get("intent") or {}).get("budget_tier") in set(args.tiers.upper())
        and (l.get("intent") or {}).get("contact_priority") == "call"
    )
    print(f"CSV: {csv_path}")
    print(f"Zeilen (A/B + call): {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

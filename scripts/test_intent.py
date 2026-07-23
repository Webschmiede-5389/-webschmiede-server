#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "akquise"))

from engine import merge_config
from enrichment import score_from_signals
from intent import derive_intent

report_path = ROOT / "docs/akquise/reports/2026-07-15-gastro.json"
if len(sys.argv) > 1:
    report_path = Path(sys.argv[1])

old = json.loads(report_path.read_text(encoding="utf-8"))
cfg = merge_config("gastro")

for name_filter in ("Anno Pief", "Mangal", "Kuchenheimer"):
    for l in old["leads"]:
        if name_filter not in l.get("name", ""):
            continue
        sig = l.get("signals") or {}
        s, p, _ = score_from_signals(l, sig, cfg)
        i = derive_intent(l, sig, cfg)
        print(f"\n=== {l['name']} ===")
        print(f"Budget: {i.get('budget_tier')} | Offenheit: {i.get('openness_label')} ({i.get('openness_tier')})")
        print(f"Umsatz: {i.get('revenue_label')} | {i.get('revenue_uplift')}")
        print(f"Probleme: {i.get('problems_summary')}")
        print(f"Anrufen? {i.get('contact_priority')} — {i.get('successor_hint')}")
        for pbl in i.get("problems") or []:
            print(f"  - {pbl.get('label')} → {pbl.get('automation','')}")

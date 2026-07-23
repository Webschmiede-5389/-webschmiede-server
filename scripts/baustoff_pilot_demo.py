#!/usr/bin/env python3
"""Demo Baustoff-Pilot lokal (ohne Server): Parse, Compare, Complaint."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

import b2b_baustoff as bb  # noqa: E402


def main() -> int:
    sample_wa = (
        "Du, ich brauche fuer heute Nachmittag noch 10 Sack Knauf Rotband "
        "und 20 CW Profil nach Mechernich"
    )
    order = bb.parse_whatsapp_order(sample_wa, from_phone="+491701234567")
    print("=== WA ORDER ===")
    print(json.dumps(order, ensure_ascii=False, indent=2)[:1200])

    csv_a = "artnr;name;preis;lieferant\nPROF-CW100;CW-Profil 100;3.20;LieferantX\nKNAUF-RB-25;Rotband 25kg;14.90;LieferantX\n"
    csv_b = "artnr;name;preis;lieferant\nPROF-CW100;CW-Profil 100;3.46;LieferantY\nKNAUF-RB-25;Rotband 25kg;14.20;LieferantY\n"
    cmp = bb.compare_price_lists(csv_a.encode(), csv_b.encode(), label_a="X", label_b="Y")
    print("\n=== COMPARE BRIEFING ===")
    for line in cmp["morning_briefing"]:
        print("-", line)

    comp = bb.classify_complaint(
        "Auftrag 45892 – Gipskartonplatten gebrochen angekommen, Fotos im Anhang. Bitte Ersatz.",
        subject="Reklamation Transportschaden",
    )
    print("\n=== COMPLAINT ===")
    print(comp["ticket"]["staff_summary"])

    print("\n=== PILOT ===")
    print(bb.pilot_pack()["pitch_30_days"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

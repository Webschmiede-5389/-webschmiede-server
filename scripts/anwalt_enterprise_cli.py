#!/usr/bin/env python3
"""CLI: Anwalt Enterprise-Paket (DocuSeal-Felder + AVV-Hinweis)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

import agency_anwalt as anwalt  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Anwalt Enterprise-Paket")
    p.add_argument("--firma", required=True)
    p.add_argument("--kontakt", default="")
    p.add_argument("--leistungen", default="")
    p.add_argument("--budget", default="")
    p.add_argument("--no-zero-retention", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    pack = anwalt.enterprise_pack(
        firma=args.firma,
        kontakt=args.kontakt,
        leistungen=args.leistungen,
        budget=args.budget,
        zero_retention=not args.no_zero_retention,
    )
    if args.json:
        print(json.dumps(pack, ensure_ascii=False, indent=2))
    else:
        print(pack["markdown"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""CLI: Anwalt 3-Stufen-Pipeline (Entwurf -> AVV -> Endkontrolle)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

import agency_anwalt as anwalt  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Anwalt 3-Stufen-Pipeline")
    p.add_argument("--firma", required=True)
    p.add_argument("--kontakt", default="")
    p.add_argument("--leistungen", default="")
    p.add_argument("--budget", default="")
    p.add_argument("--no-zero-retention", action="store_true")
    p.add_argument("--stage", type=int, choices=(1, 2, 3), help="Nur eine Stufe")
    p.add_argument("--json", action="store_true")
    p.add_argument("--out", default="", help="Markdown-Datei schreiben")
    args = p.parse_args()
    kw = dict(
        firma=args.firma,
        kontakt=args.kontakt,
        leistungen=args.leistungen,
        budget=args.budget,
        zero_retention=not args.no_zero_retention,
    )
    if args.stage == 1:
        pack = anwalt.stage1_entwurf(**kw)
        body = pack["document"]
    elif args.stage == 2:
        pack = anwalt.stage2_avv(**kw)
        body = pack["document"]
    elif args.stage == 3:
        pack = anwalt.pipeline_3_stufen(**kw)
        body = pack["protokoll"]
    else:
        pack = anwalt.pipeline_3_stufen(**kw)
        body = pack["markdown"]
    if args.out:
        Path(args.out).write_text(body, encoding="utf-8")
        print(f"geschrieben: {args.out} ampel={pack.get('ampel', '-')}")
    elif args.json:
        print(json.dumps(pack, ensure_ascii=False, indent=2))
    else:
        sys.stdout.buffer.write((body + "\n").encode("utf-8", errors="replace"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""n8n-Workflows fuer einen Kunden anlegen (pro Kunden-ID getrennt)."""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from n8n_kunde import provision_via_ssh, build_kunde_workflows, _load_kunde_json, provision_kunde


def main():
    ap = argparse.ArgumentParser(description="n8n Workflows pro Kunde provisionieren")
    ap.add_argument("kunde_id", help="z.B. SHY002, HWK001")
    ap.add_argument("--dry-run", action="store_true", help="Nur Workflows lokal anzeigen")
    args = ap.parse_args()
    kid = args.kunde_id.upper()

    if args.dry_run:
        kunde, _ = _load_kunde_json(kid)
        wfs = build_kunde_workflows(kunde)
        print(json.dumps([{"name": w["name"]} for w in wfs], indent=2, ensure_ascii=False))
        return

    result = provision_kunde(kid)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

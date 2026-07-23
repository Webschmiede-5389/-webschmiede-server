#!/usr/bin/env python3
"""Lexware-Verbindung für einen Kunden testen."""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "app", "backend"))

from integrations import integrations_config, load_kunde_json
from integrations.lexware import test_connection


def main() -> int:
    p = argparse.ArgumentParser(description="Lexware Office API testen")
    p.add_argument("kunde_id", nargs="?", default="SHY001", help="Kunden-ID")
    args = p.parse_args()
    kid = args.kunde_id.strip().upper()

    kunde = load_kunde_json(kid)
    if not kunde:
        print(f"Kunde {kid} nicht gefunden in kunden/")
        return 1

    cfg = integrations_config(kunde)
    result = test_connection(kunde, cfg)
    if result.get("ok"):
        print(f"OK — Lexware verbunden ({result.get('organization')})")
        return 0
    print(f"Fehler: {result.get('error')}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Requesty Tagesverbrauch anzeigen (ohne Secrets)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

import requesty_client as rq  # noqa: E402


def main() -> int:
    u = rq.usage_today()
    k = rq.key_info()
    print(json.dumps({"usage": u, "key": k, "image_budget": rq.budget_guard(kind="image")}, indent=2))
    if u.get("ok"):
        print(
            f"\nHeute: ${u.get('spend')} · "
            f"{u.get('images')} Bilder · {u.get('completions')} Chats · "
            f"{u.get('transcriptions')} STT"
        )
    return 0 if u.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

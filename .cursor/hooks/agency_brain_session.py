#!/usr/bin/env python3
"""sessionStart: Agency-Hirn Kontext in neue Chats injizieren."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTING = ROOT / ".cursor" / "brain-routing.md"

CTX = """# Agency-Hirn (scharf)

Du bist im Webschmiede-Repo. Vor der Antwort:

1. Lies `.cursor/brain-routing.md` (wird bei jeder User-Nachricht aktualisiert).
2. Arbeite `playbook` / Mitarbeiter in der Reihenfolge ab.
3. Kein Auto-Send an Kunden, keine Käufe ohne OK.

Fallback wenn Routing-Datei fehlt:
`python scripts/agency_brain_cli.py "<Nachricht>"`
"""


def main() -> int:
    try:
        json.loads(sys.stdin.read() or "{}")
    except Exception:
        pass
    extra = ""
    if ROUTING.is_file():
        extra = "\n\n## Letztes Routing\n" + ROUTING.read_text(encoding="utf-8", errors="replace")[:2500]
    out = {"additional_context": CTX + extra}
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""beforeSubmitPrompt: User-Nachricht durch Agency-Hirn jagen, Routing-Datei schreiben."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTING = ROOT / ".cursor" / "brain-routing.md"
SKIP_RE = re.compile(
    r"^(ok|ja|nein|danke|thx|ds|hm+|test|\.+|warum|was\?)$",
    re.I,
)


def _skip(prompt: str) -> bool:
    p = (prompt or "").strip()
    if len(p) < 8:
        return True
    if SKIP_RE.match(p):
        return True
    # reine Meta-Chat-Befehle
    if p.lower() in ("weiter", "mach weiter", "stopp", "stop"):
        return True
    return False


def main() -> int:
    raw = sys.stdin.read() or "{}"
    try:
        data = json.loads(raw)
    except Exception:
        data = {}
    prompt = (data.get("prompt") or data.get("message") or "").strip()

    # Immer continue – Hirn darf Chat nicht blockieren
    if _skip(prompt):
        sys.stdout.write(json.dumps({"continue": True}))
        return 0

    sys.path.insert(0, str(ROOT / "app" / "backend"))
    try:
        import agency_brain as brain

        # Schneller Dispatch: ohne Dual-SSH wenn reine Text-Skills
        # Nils/Service brauchen SSH – timeout-sicher im Modul
        result = brain.process(
            prompt,
            source="cursor-hook",
            dispatch=True,
            include_commander=False,
            max_agents=4,
            fast=True,
        )
        md = [
            "# Agency-Hirn Routing (auto)",
            "",
            result.get("summary") or "",
            "",
            "## Playbook",
            result.get("playbook") or "",
            "",
            f"Agents: {', '.join(result.get('agents') or [])}",
            f"Sharp: {result.get('sharp')}",
            "",
            "## Hinweis",
            "Vom Cursor-Hook geschrieben. Agent: dieses Playbook jetzt ausfuehren.",
            result.get("honest") or "",
        ]
        ROUTING.parent.mkdir(parents=True, exist_ok=True)
        ROUTING.write_text("\n".join(md), encoding="utf-8")
    except Exception as exc:
        ROUTING.parent.mkdir(parents=True, exist_ok=True)
        ROUTING.write_text(
            f"# Agency-Hirn Routing\n\nFEHLER: {exc}\n\n"
            f"Manuell: python scripts/agency_brain_cli.py \"{prompt[:200]}\"\n",
            encoding="utf-8",
        )

    sys.stdout.write(json.dumps({"continue": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

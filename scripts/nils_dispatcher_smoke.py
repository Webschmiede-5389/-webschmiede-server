#!/usr/bin/env python3
"""Smoke-Test Nils Dispatcher: Classify + Strip (+ optional Ollama-Call)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

import nils_dispatcher as d  # noqa: E402


def main() -> int:
    cases = [
        ("Wie spät haben wir auf?", "A"),
        ("Schreib mir eine Architektur für den Sales-Funnel und Code-Skizze", "B"),
        ("Extrahiere diesen Lieferschein als JSON", "C"),
    ]
    print("=== classify ===")
    for text, expect in cases:
        got = d.classify_route(text)
        ok = "OK" if got == expect else "FAIL"
        print(f"  [{ok}] expect={expect} got={got} :: {text[:50]}")

    sample = (
        "Kunde Max Mustermann, Mail max@example.com, Tel 02443 3088966, "
        "IBAN DE89370400440532013000, Key sk-abc123456789012345678901234"
    )
    masked, counts = d.strip_pii(sample)
    print("=== strip_pii ===")
    print("  counts", counts)
    print("  masked", masked[:160])
    assert "[EMAIL]" in masked
    assert "[IBAN]" in masked
    assert "[SECRET]" in masked

    print("=== readiness ===")
    r = d.readiness()
    print("  ollama_ok", r.get("ollama_ok"), "openrouter", r.get("openrouter_key"))
    print("  routes A", r.get("routes", {}).get("A", [])[:3])

    if r.get("ollama_ok"):
        print("=== live Route A (Ollama) ===")
        out = d.dispatch(
            [
                {"role": "system", "content": "Antworte mit einem Wort: pong"},
                {"role": "user", "content": "ping"},
            ],
            route="A",
            max_tokens=20,
            temperature=0,
            timeout=60,
        )
        print("  ok", out.get("ok"), "provider", out.get("provider"), "model", out.get("model"))
        print("  reply", (out.get("reply") or "")[:80])
        print("  attempts", out.get("attempts"))
    else:
        print("=== live skip (kein Ollama) ===")

    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

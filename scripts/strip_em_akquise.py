"""Em-Dash in Akquise-Texten entfernen (Pitch/Report-Quelle)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(r"C:\Users\kumex\OneDrive\Desktop\Jarvis\Server\akquise")
EM = "\u2014"
EN = "\u2013"


def fix(text: str) -> str:
    text = text.replace(f'"{EM}"', f'"{EN}"')
    text = text.replace(f"'{EM}'", f"'{EN}'")
    text = text.replace(f"or {EM!r}", f"or {EN!r}")
    text = text.replace(f'else "{EM}"', f'else "{EN}"')
    text = text.replace(f"else '{EM}'", f"else '{EN}'")
    text = re.sub(rf"\s*{EM}\s*", ", ", text)
    # Docstring titles oft "Modul, Beschreibung" ok or use middot for first line
    text = text.replace('"""Webschmiede Akquise Engine, Apify', '"""Webschmiede Akquise Engine · Apify')
    text = text.replace('"""Re-Scan Diff, Trigger', '"""Re-Scan Diff · Trigger')
    text = text.replace('"""Meta Ad Library, Werbe', '"""Meta Ad Library · Werbe')
    text = text.replace('"""Handelsregister / North Data, GF', '"""Handelsregister / North Data · GF')
    text = text.replace('"""Zahlungsbereitschaft schätzen, Zeit', '"""Zahlungsbereitschaft schätzen · Zeit')
    return text


def main() -> None:
    for p in list(ROOT.rglob("*.py")) + list(ROOT.rglob("*.json")):
        raw = p.read_text(encoding="utf-8")
        if EM not in raw:
            continue
        new = fix(raw)
        p.write_text(new, encoding="utf-8")
        print(f"{p.relative_to(ROOT.parent)}: {raw.count(EM)} -> {new.count(EM)}")


if __name__ == "__main__":
    main()

"""KI-Gedankenstriche (–/—) in Kundentexten entfernen. Preisbereiche 950 – 1.500 bleiben."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(r"C:\Users\kumex\OneDrive\Desktop\Jarvis\Server")

FILES = [
    ROOT / "agency-web/src/pages/HomePage.tsx",
    ROOT / "agency-web/src/pages/MarkenhinweisePage.tsx",
    ROOT / "agency-web/src/pages/ImpressumPage.tsx",
    ROOT / "agency-web/src/pages/DatenschutzPage.tsx",
    ROOT / "agency-web/src/components/IntegrationsSection.tsx",
    ROOT / "agency-web/src/components/Layout.tsx",
    ROOT / "agency-web/src/data/integrations.ts",
    ROOT / "agency-web/public/angebote.json",
    ROOT / "agency-web/public/angebote.html",
    ROOT / "app/static/angebote.html",
    ROOT / "app/static/angebote.json",
    ROOT / "app/static/ci/angebot-vorlage.html",
    ROOT / "app/static/ci/flyer-vorlage.html",
    ROOT / "app/static/agency-hub.html",
]

DASHES = "\u2014\u2013"  # em + en


def fix(text: str) -> str:
    # Sentence break dash: not between digits (keep ranges)
    text = re.sub(rf"(?<!\d)\s*[{DASHES}]\s*(?!\d)", ", ", text)
    # Title leftovers like "Festpreise, Webschmiede" from above is fine;
    # or prefer middot for titles in HTML meta/title
    text = text.replace("Festpreise, Webschmiede", "Festpreise · Webschmiede")
    text = text.replace("Branche, Webschmiede Digitale", "Branche · Webschmiede Digitale")
    text = re.sub(
        r"\$\{ind\.label\}, Festpreise · Webschmiede",
        "${ind.label} · Festpreise · Webschmiede",
        text,
    )
    text = re.sub(
        r"`\$\{ind\.label\}, Festpreise",
        "`${ind.label} · Festpreise",
        text,
    )
    # Empty placeholder alone (catalog date)
    text = re.sub(r">,\s*<", ">–<", text)  # accidental from span
    text = text.replace(">'\u2014'||", "")
    # Fix catalog fallback if mangled
    text = re.sub(
        r"catalog-date.*?\|\| '[^,']*'",
        lambda m: m.group(0).replace(", ", "–") if False else m.group(0),
        text,
    )
    # Standalone empty placeholders: ", " wrongly from — alone in || '—'
    text = text.replace("|| ', '", "|| '–'")
    text = text.replace("textContent = data.updated || ', '", "textContent = data.updated || '–'")
    text = text.replace('id="catalog-date">, </span>', 'id="catalog-date">–</span>')
    text = text.replace("id=\"catalog-date\">, </span>", "id=\"catalog-date\">–</span>")
    # Agency hub quote: AI cadence with "entlasten — robust"
    text = text.replace("entlasten, robust wie Handwerk, smart wie KI", "entlasten. Robust wie Handwerk.")
    text = text.replace("„Ich baue Systeme, die entlasten, robust wie Handwerk.", "„Ich baue Systeme, die mitarbeiten.")
    return text


def main() -> None:
    for p in FILES:
        if not p.exists():
            print("MISSING", p)
            continue
        raw = p.read_text(encoding="utf-8")
        new = fix(raw)
        before = sum(raw.count(d) for d in DASHES)
        after = sum(new.count(d) for d in DASHES)
        if new != raw:
            p.write_text(new, encoding="utf-8")
            print(f"fixed {p.relative_to(ROOT)}: dashes {before} -> {after}")
        else:
            print(f"ok {p.name}: {before}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Design lint: flag NEW legacy colors / W-placeholders outside allowlist.

Exit 0 if no new violations vs baseline allowlist file.
Does not fail the whole repo for known legacy paths.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST = ROOT / "config" / "design_lint_allowlist.txt"

PATTERNS = [
    (re.compile(r"(?<![0-9A-Fa-f])#C9A84C(?![0-9A-Fa-f])", re.I), "legacy_gold"),
    (re.compile(r"(?<![0-9A-Fa-f])#E8600A(?![0-9A-Fa-f])", re.I), "leads_orange"),
    (re.compile(r"brand-mark[^>]*>\s*W\s*<", re.I), "w_placeholder"),
    (re.compile(r"javascript:", re.I), "javascript_url"),
]


def strip_css_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def strip_html_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)

SCAN_GLOBS = [
    "app/static/**/*.html",
    "app/static/**/*.css",
    "app/static/ci/webschmiede-*.css",
    "app/backend/templates/**/*.html",
    "agency-web/src/**/*.{tsx,ts,css}",
]

# Always scanned for NEW design-system files (must be clean)
STRICT_GLOBS = [
    "app/static/ci/webschmiede-tokens.css",
    "app/static/ci/webschmiede-base.css",
    "app/static/ci/webschmiede-components.css",
    "app/static/ci/webschmiede-layout.css",
    "app/static/ci/webschmiede-utilities.css",
    "app/static/ci/webschmiede-app.css",
    "app/backend/templates/design_system/**/*.html",
    "app/backend/templates/shared/ui/**/*.html",
]


def load_allowlist() -> set[str]:
    if not ALLOWLIST.is_file():
        return set()
    out = set()
    for line in ALLOWLIST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.add(line.replace("\\", "/"))
    return out


def iter_files(globs: list[str]) -> list[Path]:
    files: list[Path] = []
    for g in globs:
        files.extend(ROOT.glob(g))
    # unique
    return sorted({p.resolve() for p in files if p.is_file()})


def main() -> int:
    allow = load_allowlist()
    new_violations: list[str] = []
    legacy_hits = 0

    for path in iter_files(STRICT_GLOBS):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if path.suffix == ".css":
            text = strip_css_comments(text)
        elif path.suffix in {".html", ".htm"}:
            text = strip_html_comments(text)
        rel = path.relative_to(ROOT).as_posix()
        for cre, kind in PATTERNS:
            if kind == "javascript_url":
                continue
            if cre.search(text):
                new_violations.append(f"{rel}: {kind}")

    # Broader scan: only report if not allowlisted
    for path in iter_files(SCAN_GLOBS):
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        if path.suffix == ".css":
            text = strip_css_comments(text)
        for cre, kind in PATTERNS:
            if not cre.search(text):
                continue
            key = f"{rel}:{kind}"
            if key in allow or rel in allow:
                legacy_hits += 1
                continue
            if "webschmiede-app" in rel or "design_system" in rel or "shared/ui" in rel:
                new_violations.append(key)
            elif kind == "javascript_url":
                new_violations.append(key)

    if new_violations:
        print("FAIL new design lint violations:")
        for v in sorted(set(new_violations)):
            print(" -", v)
        return 1
    print(f"OK design lint (legacy allowlisted hits noted: {legacy_hits})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

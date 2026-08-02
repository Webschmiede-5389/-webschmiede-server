#!/usr/bin/env python3
"""Controlled sync: shared Design System → CRM static/ws (checksummed).

Preferred integration path for SCHRITT 3 (no CDN, no symlink, no CRM-owned tokens).
Source of truth remains webschmiede-server app/static/{ci,brand/webschmiede}.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CRM = ROOT.parent / "crm"
CI_FILES = (
    "webschmiede-tokens.css",
    "webschmiede-base.css",
    "webschmiede-layout.css",
    "webschmiede-components.css",
    "webschmiede-utilities.css",
    "webschmiede-app.css",
    "webschmiede-ui.js",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sync(crm_root: Path, source_commit: str) -> Path:
    src_ci = ROOT / "app" / "static" / "ci"
    src_brand = ROOT / "app" / "static" / "brand" / "webschmiede"
    dest_root = crm_root / "app" / "static" / "ws"
    dest_ci = dest_root / "ci"
    dest_brand = dest_root / "brand" / "webschmiede"
    dest_ci.mkdir(parents=True, exist_ok=True)
    dest_brand.mkdir(parents=True, exist_ok=True)

    for name in CI_FILES:
        src = src_ci / name
        if not src.is_file():
            raise FileNotFoundError(f"missing source {src}")
        shutil.copy2(src, dest_ci / name)

    for src in src_brand.iterdir():
        if src.is_file():
            shutil.copy2(src, dest_brand / src.name)

    lines = [
        "version: 1",
        f"source_commit: {source_commit}",
        f"synced_at: {datetime.now(timezone.utc).isoformat()}",
        "source_of_truth: webschmiede-server/app/static/{ci,brand/webschmiede}",
        "files:",
    ]
    for path in sorted(dest_root.rglob("*")):
        if not path.is_file() or path.name == "VERSION.yaml":
            continue
        rel = "/" + path.relative_to(dest_root).as_posix()
        lines.append(f"  - path: {rel}")
        lines.append(f"    sha256: {_sha256(path)}")
        lines.append(f"    bytes: {path.stat().st_size}")

    version_path = dest_root / "VERSION.yaml"
    version_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return version_path


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--crm-root", type=Path, default=DEFAULT_CRM)
    p.add_argument("--source-commit", default="53b39fb")
    args = p.parse_args(argv)
    if not args.crm_root.is_dir():
        print(f"CRM root missing: {args.crm_root}", file=sys.stderr)
        return 1
    out = sync(args.crm_root.resolve(), args.source_commit)
    print("OK", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

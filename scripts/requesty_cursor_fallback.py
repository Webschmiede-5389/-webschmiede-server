#!/usr/bin/env python3
"""Cursor ↔ Requesty Fallback umschalten (nur bei Limit einschalten)."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

APPDATA = Path(os.environ["APPDATA"])
SETTINGS = APPDATA / "Cursor" / "User" / "settings.json"
BACKUP = APPDATA / "Cursor" / "User" / "settings.requesty-backup.json"
MARKER = APPDATA / "Cursor" / "User" / "requesty-fallback.active"
ROOT = Path(__file__).resolve().parents[1]
VBS = ROOT / "scripts" / "start_requesty_cursor_router_hidden.vbs"


def read_settings() -> dict:
    if not SETTINGS.is_file():
        return {}
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_settings(data: dict) -> None:
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def router_up() -> bool:
    try:
        urllib.request.urlopen("http://127.0.0.1:8787/v1/models", timeout=3)
        return True
    except Exception:
        return False


def stop_router() -> None:
    # Windows: Prozesse auf Port 8787 beenden
    ps = (
        "Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue "
        "| ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True,
        text=True,
        check=False,
    )


def enable() -> int:
    data = read_settings()
    if not MARKER.exists() and SETTINGS.is_file():
        BACKUP.write_text(SETTINGS.read_text(encoding="utf-8"), encoding="utf-8")

    data["cursor.models.useOpenAI"] = True
    data["cursor.models.openaiBaseUrl"] = "http://127.0.0.1:8787/v1"
    data["cursor.models.openaiApiKey"] = "local-requesty-router"
    write_settings(data)

    if not router_up():
        subprocess.Popen(
            ["wscript.exe", str(VBS)],
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(10):
            time.sleep(0.5)
            if router_up():
                break

    MARKER.write_text(f"active {datetime.now(timezone.utc).isoformat()}\n", encoding="utf-8")
    print("Requesty-Fallback AKTIV")
    print("1) Cursor: Reload Window (Ctrl+Shift+P)")
    print("2) Models: requesty-auto hinzufuegen und auswaehlen")
    print("Zurueck: python scripts/requesty_cursor_fallback.py disable")
    print("Router OK" if router_up() else "WARN: Router antwortet noch nicht")
    return 0


def disable() -> int:
    stop_router()
    if BACKUP.is_file():
        SETTINGS.write_text(BACKUP.read_text(encoding="utf-8"), encoding="utf-8")
        BACKUP.unlink(missing_ok=True)
    else:
        data = read_settings()
        for k in (
            "cursor.models.useOpenAI",
            "cursor.models.openaiBaseUrl",
            "cursor.models.openaiApiKey",
        ):
            data.pop(k, None)
        write_settings(data)
    MARKER.unlink(missing_ok=True)
    print("Requesty-Fallback AUS - Cursor nutzt wieder das Abo.")
    print("Bitte Cursor: Reload Window")
    return 0


def status() -> int:
    active = MARKER.exists()
    print(f"fallback={'AN' if active else 'AUS'}")
    print(f"router={'UP' if router_up() else 'DOWN'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Requesty nur bei Cursor-Limit")
    ap.add_argument("action", choices=["enable", "disable", "status"])
    args = ap.parse_args()
    if args.action == "enable":
        return enable()
    if args.action == "disable":
        return disable()
    return status()


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Telegram Webhook bei BotFather/API setzen (nach Token in Secrets)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))
sys.path.insert(0, str(ROOT))

# Secrets laden
for path in (ROOT / "deploy.secrets.local", Path("/root/app/deploy.secrets.local")):
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        break

import telegram_ops as tg  # noqa: E402


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else None
    print("Token gesetzt:", bool(tg.bot_token()))
    print("Owner chats:", tg.owner_chat_ids())
    result = tg.set_webhook(url)
    print(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

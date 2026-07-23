#!/usr/bin/env python3
"""Send a plain customer email via agency SMTP (BCC from AGENCY_MAIL_BCC)."""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

BACKEND = os.path.join(ROOT, "app", "backend")
if not os.path.isdir(BACKEND):
    BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)

from agency_mail import send_html_email
from email_templates import email_shell


def plain_to_html(text: str) -> str:
    parts = []
    for block in text.strip().split("\n\n"):
        block = block.strip()
        if not block:
            continue
        lines = "<br>".join(line.strip() for line in block.split("\n"))
        parts.append(f"<p style='margin:0 0 16px;'>{lines}</p>")
    return "".join(parts)


def main() -> None:
    p = argparse.ArgumentParser(description="Kunden-Mail senden (Agency SMTP)")
    p.add_argument("--to", required=True, help="Empfänger")
    p.add_argument("--subject", required=True, help="Betreff")
    p.add_argument("--body-file", help="Plain-Text Datei")
    p.add_argument("--body", help="Plain-Text direkt")
    args = p.parse_args()

    if args.body_file:
        with open(args.body_file, encoding="utf-8") as f:
            text = f.read()
    elif args.body:
        text = args.body
    else:
        raise SystemExit("--body oder --body-file nötig")

    html = email_shell(
        hero_title=args.subject,
        body_html=plain_to_html(text),
        preheader=text.split("\n")[0][:120],
    )
    send_html_email(to=args.to, subject=args.subject, html=html, text=text)
    print(f"Gesendet an {args.to} (BCC laut AGENCY_MAIL_BCC)")


if __name__ == "__main__":
    main()

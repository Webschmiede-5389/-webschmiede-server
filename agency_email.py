"""Agency SMTP (import path for scripts at repo root)."""
import os
import sys

_BACKEND = os.path.join(os.path.dirname(__file__), "app", "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from agency_mail import build_message, load_agency_smtp, send_html_email  # noqa: F401

__all__ = ["build_message", "load_agency_smtp", "send_html_email"]

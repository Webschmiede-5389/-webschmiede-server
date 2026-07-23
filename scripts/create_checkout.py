#!/usr/bin/env python3
"""Stripe Checkout-Link für Kunden erstellen.

  python scripts/create_checkout.py SHY001 pro
  python scripts/create_checkout.py SHY001 starter --email kunde@example.com
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app", "backend"))
sys.path.insert(0, ROOT)

from stripe_billing import create_checkout_session, stripe_configured


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kunde_id")
    ap.add_argument("package", nargs="?", default="pro", choices=["pro", "starter"])
    ap.add_argument("--email", help="Override Kunden-E-Mail")
    args = ap.parse_args()

    if not stripe_configured():
        raise SystemExit(
            "STRIPE_SECRET_KEY fehlt in deploy.secrets.local\n"
            "Siehe docs/agency/stripe-setup.md"
        )

    r = create_checkout_session(
        kunde_id=args.kunde_id,
        package_id=args.package,
        customer_email=args.email,
    )
    print(f"\nKunde:   {r['kunde_id']}")
    print(f"Paket:   {args.package}")
    print(f"E-Mail:  {r['email']}")
    print(f"\nZahlungslink (an Kunden senden):\n{r['url']}\n")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Lädt Integrations-Logos nach agency-web/public/integrations/."""

from __future__ import annotations

import os
import shutil
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(__file__))
OUT = os.path.join(ROOT, "agency-web", "public", "integrations")
SI = "https://cdn.jsdelivr.net/npm/simple-icons@v11/icons"

# slug -> dateiname (svg)
SIMPLE_ICONS = {
    "google": "google.svg",
    "hubspot": "hubspot.svg",
    "meta": "meta.svg",
    "whatsapp": "whatsapp.svg",
    "stripe": "stripe.svg",
    "caldotcom": "calcom.svg",
    "salesforce": "salesforce.svg",
    "pipedrive": "pipedrive.svg",
    "microsoft": "microsoft.svg",
    "zoho": "zoho.svg",
    "odoo": "odoo.svg",
    "monday": "monday.svg",
    "mailchimp": "mailchimp.svg",
    "brevo": "brevo.svg",
    "activecampaign": "activecampaign.svg",
    "paypal": "paypal.svg",
    "klarna": "klarna.svg",
    "slack": "slack.svg",
    "wolt": "wolt.svg",
    "ubereats": "ubereats.svg",
    "sumup": "sumup.svg",
}

# Wenn Simple-Icons fehlschlägt → Favicon (domain, dateiname)
SVG_FALLBACK_FAVICON = {
    "pipedrive.com": "pipedrive.png",
    "monday.com": "monday.png",
    "activecampaign.com": "activecampaign.png",
    "wolt.com": "wolt.png",
    "sumup.com": "sumup.png",
    "plancraft.com": "plancraft.png",
}

# Direkt-URL wenn Favicon-Dienste scheitern
DIRECT_URLS = {
    "plancraft.png": "https://plancraft.de/favicon.ico",
}

# slug nicht in simple-icons → favicon
FAVICON_ONLY = {
    "n8n.io": "n8n.svg",
    "lightspeedhq.com": "lightspeed.svg",
    "datev.de": "datev.svg",
}

# domain -> png via Google favicon service
FAVICONS = {
    "lexware.de": "lexware.png",
    "sevdesk.de": "sevdesk.png",
    "gastronovi.com": "gastronovi.png",
    "ready2order.com": "ready2order.png",
    "orderbird.com": "orderbird.png",
    "lieferando.de": "lieferando.png",
    "hero-software.de": "hero.png",
    "tooltime.de": "tooltime.png",
    "craftboxx.de": "craftboxx.png",
    "das-programm.io": "das-programm.png",
    "pds.de": "pds.png",
    "seven.io": "seven.png",
    "bitrix24.de": "bitrix24.png",
    "weclapp.com": "weclapp.png",
    "teamleader.eu": "teamleader.png",
    "freshworks.com": "freshworks.png",
    "centralstationcrm.de": "centralstationcrm.png",
    "gohighlevel.com": "gohighlevel.png",
    "fastbill.com": "fastbill.png",
    "billomat.com": "billomat.png",
    "openhandwerk.de": "openhandwerk.png",
}


def fetch(url: str, dest: str) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Webschmiede-Logo-Fetch/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
        if len(data) < 80:
            return False
        with open(dest, "wb") as f:
            f.write(data)
        return True
    except Exception as exc:
        print(f"  FAIL {dest}: {exc}")
        return False


def copy_webschmiede_logo() -> bool:
    """Eigenes Logo für Webschmiede CRM-Kachel."""
    candidates = [
        os.path.join(ROOT, "agency-web", "public", "webschmiede-icon.png"),
        os.path.join(ROOT, "app", "static", "ci", "webschmiede-icon.png"),
    ]
    dest = os.path.join(OUT, "webschmiede.png")
    for src in candidates:
        if os.path.isfile(src):
            shutil.copy2(src, dest)
            print(f"COPY {src} -> webschmiede.png")
            return True
    print("  SKIP webschmiede.png (Quelle nicht gefunden)")
    return False


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    ok = fail = 0

    for slug, fname in SIMPLE_ICONS.items():
        dest = os.path.join(OUT, fname)
        url = f"{SI}/{slug}.svg"
        print(f"SVG {slug} -> {fname}")
        if fetch(url, dest):
            ok += 1
        else:
            fail += 1

    for domain, fname in SVG_FALLBACK_FAVICON.items():
        dest = os.path.join(OUT, fname)
        if os.path.isfile(dest):
            continue
        url = f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
        print(f"FALLBACK {domain} -> {fname}")
        if fetch(url, dest):
            ok += 1
        else:
            fail += 1

    for domain, fname in FAVICON_ONLY.items():
        dest = os.path.join(OUT, fname)
        url = f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
        print(f"FAV {domain} -> {fname}")
        if fetch(url, dest):
            ok += 1
        else:
            fail += 1

    for domain, fname in FAVICONS.items():
        dest = os.path.join(OUT, fname)
        url = f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
        print(f"PNG {domain} -> {fname}")
        if fetch(url, dest):
            ok += 1
        else:
            fail += 1

    if copy_webschmiede_logo():
        ok += 1

    for fname, url in DIRECT_URLS.items():
        dest = os.path.join(OUT, fname)
        print(f"DIRECT {url} -> {fname}")
        if fetch(url, dest):
            ok += 1
        else:
            fail += 1

    print(f"\nFertig: {ok} ok, {fail} fehlgeschlagen -> {OUT}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

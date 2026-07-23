"""Restliche Em-Dashes in Backend-Strings (nicht nur Docstrings)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(r"C:\Users\kumex\OneDrive\Desktop\Jarvis\Server")
EM = "\u2014"
EN = "\u2013"

FILES = [
    "app/backend/agency_chat.py",
    "app/backend/inbox_agent.py",
    "app/backend/agency_secrets.py",
    "app/backend/main.py",
    "app/backend/client_setup.py",
    "app/backend/stripe_billing.py",
    "app/backend/agency_cockpit.py",
    "app/backend/agency_packages.py",
    "app/backend/agency_mail.py",
    "app/backend/email_templates.py",
]

POST = [
    ("Jarvis, Kunde", "Jarvis · Kunde"),
    ("Jarvis, **Agency", "Jarvis · **Agency"),
    ("Agency Jarvis, Chat", "Agency Jarvis · Chat"),
    ("Agency cockpit, Kunden", "Agency cockpit · Kunden"),
    ("Webschmiede Agency, Pakete", "Webschmiede Agency · Pakete"),
    ("Agency SMTP, headers", "Agency SMTP · headers"),
    ("Posteingang heute, ", "Posteingang heute · "),
    ("Offen, manuell", "Offen · manuell"),
    ("f\"• {k['id']}, {k['name']}", "f\"• {k['id']} · {k['name']}"),
    ("**{d.get('name')}** ({kid}), Status:", "**{d.get('name')}** ({kid}) · Status:"),
    ("</strong>, {p.get", "</strong> · {p.get"),
    ("</strong>, {u.get", "</strong> · {u.get"),
    ("Vorschau: {r.get('host')}, {r.get", "Vorschau: {r.get('host')} · {r.get"),
    ("Webroot **{r.get('webroot')}**, {r.get", "Webroot **{r.get('webroot')}** · {r.get"),
    ("Noch eine Aktion offen, **Ja**", "Noch eine Aktion offen. **Ja**"),
    ("getrennt, hier steuerst", "getrennt. Hier steuerst"),
    ("• **Alle Kunden**, Übersicht", "• **Alle Kunden** · Übersicht"),
    ("• **Status SHY001**, mit", "• **Status SHY001** · mit"),
    ("table layout, Webschmiede", "table layout · Webschmiede"),
    ("Cal.com, Seminare", "Cal.com · Seminare"),
    ("Festpreise), für Website", "Festpreise) · für Website"),
    ("auf dem Server, lokal:", "auf dem Server. Lokal:"),
    ("beim Kunden, customer_email", "beim Kunden. customer_email"),
    ("sk_live_…, Developers", "sk_live_… · Developers"),
    ("whsec_…, Endpoint:", "whsec_… · Endpoint:"),
    ("Akquise“, Places", "Akquise“ · Places"),
    ("Handelsregister, optional", "Handelsregister · optional"),
    ("deploy.secrets.local, Agency", "deploy.secrets.local · Agency"),
    ("Ziel-E-Mail, AGENCY", "Ziel-E-Mail. AGENCY"),
    ("Google API: {st}, {data", "Google API: {st} · {data"),
]


def fix(text: str) -> str:
    text = text.replace(f"'{EM}'", f"'{EN}'")
    text = text.replace(f'"{EM}"', f'"{EN}"')
    text = re.sub(rf"\s*{EM}\s*", ", ", text)
    for a, b in POST:
        text = text.replace(a, b)
    return text


def main() -> None:
    for rel in FILES:
        p = ROOT / rel
        raw = p.read_text(encoding="utf-8")
        if EM not in raw:
            print("ok", rel)
            continue
        new = fix(raw)
        p.write_text(new, encoding="utf-8")
        print(f"fixed {rel}: {raw.count(EM)} -> {new.count(EM)}")


if __name__ == "__main__":
    main()

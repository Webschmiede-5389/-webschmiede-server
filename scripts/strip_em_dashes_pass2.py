"""Nur Em-Dash (—) in Kundentexten entfernen. En-Dash (–) bleibt für Platzhalter."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(r"C:\Users\kumex\OneDrive\Desktop\Jarvis\Server")
EM = "\u2014"
EN = "\u2013"

FILES = [
    "app/static/order.html",
    "app/static/onboarding.html",
    "app/static/seminare.html",
    "app/static/admin.html",
    "app/static/agency.html",
    "app/static/agency-setup.html",
    "app/static/agency-keys.html",
    "app/static/agency-hub.html",
    "app/static/ci/onboarding-vorlage.html",
    "app/static/ci/rechnung-vorlage.html",
    "app/static/ci/handout-vorlage.html",
    "app/static/ci/visitenkarte-vorlage.html",
    "app/static/ci/email-signatur.html",
    "app/static/ci/angebot-vorlage.html",
    "app/static/ci/flyer-vorlage.html",
    "docs/agency/rechnung-vorlage.html",
    "docs/agency/angebot-vorlage.html",
    "agency-web/README.md",
]

# Nach dem Komma-Ersatz: typische Titel-/UI-Muster auf Middot/Punkt korrigieren
POST = [
    ("Admin, Snack House", "Admin · Snack House"),
    ("Admin, Webschmiede", "Admin · Webschmiede"),
    ("Agency Setup, Webschmiede", "Agency Setup · Webschmiede"),
    ("Agency Keys, Webschmiede", "Agency Keys · Webschmiede"),
    ("Agency Admin, Webschmiede", "Agency Admin · Webschmiede"),
    ("Onboarding, Webschmiede", "Onboarding · Webschmiede"),
    ("Onboarding, Kunde", "Onboarding · Kunde"),
    ("Onboarding, '", "Onboarding · '"),
    ("Seminare & Beratung, Webschmiede", "Seminare & Beratung · Webschmiede"),
    ("Jetzt bestellen, Snack House", "Jetzt bestellen · Snack House"),
    ("Rechnung, Webschmiede", "Rechnung · Webschmiede"),
    ("Angebot / Kalkulation, Webschmiede", "Angebot / Kalkulation · Webschmiede"),
    ("WebSchmiede, Digitales Handwerk", "WebSchmiede · Digitales Handwerk"),
    ("Webschmiede, Digitale Handwerkskunst", "Webschmiede · Digitale Handwerkskunst"),
    ("Webschmiede – Digitale Handwerkskunst", "Webschmiede · Digitale Handwerkskunst"),
    ("Option A, Drucken", "Option A · Drucken"),
    ("Option B, Auto-Druck", "Option B · Auto-Druck"),
    ("Option C, Netzwerk", "Option C · Netzwerk"),
    ("AGB, Online-Bestelldienst", "AGB · Online-Bestelldienst"),
    ("Pro, 1.980", "Pro · 1.980"),
    ("Starter, 998", "Starter · 998"),
    ("Fertig, Kunde öffnen", "Fertig · Kunde öffnen"),
    ("autoprint.py, läuft", "autoprint.py · läuft"),
    ("${esc(k.id)}, ${esc(k.name)}", "${esc(k.id)} · ${esc(k.name)}"),
    ("${k.id}, ${k.name}", "${k.id} · ${k.name}"),
    ("${esc(kid)}), Aktionen gelten", "${esc(kid)}). Aktionen gelten"),
    ("eingeloggt, kein Kunden-Account", "eingeloggt. Kein Kunden-Account"),
    ("**Agency-Modus**, du steuerst", "**Agency-Modus.** Du steuerst"),
    ("Link erstellt, an Kunden senden", "Link erstellt. An Kunden senden"),
    ("OK, ${d.webroot", "OK · ${d.webroot"),
    ("Vorschau: ${esc(d.host || '')}, ${esc", "Vorschau: ${esc(d.host || '')} · ${esc"),
    ("title=\"${esc(a.hint || '')}, ${srv}\"", "title=\"${esc(a.hint || '')} · ${srv}\""),
    ("`${body.name} (${wizardKundeId}), ${body.subdomain", "`${body.name} (${wizardKundeId}) · ${body.subdomain"),
    ("${o.promo_applied}, Gratis-Artikel", "${o.promo_applied}. Gratis-Artikel"),
    ("${i.name}, GRATIS", "${i.name} · GRATIS"),
    ("${i.qty}x ${i.name}, ${(i.price", "${i.qty}x ${i.name} · ${(i.price"),
    ("Noch keine Kunden, kommen automatisch", "Noch keine Kunden. Kommen automatisch"),
    ("OFFLINE, Kunden können", "OFFLINE. Kunden können"),
    ("Sofort aktiv, kein Setup", "Sofort aktiv. Kein Setup"),
    ("Automatisch, druckt ohne", "Automatisch. Druckt ohne"),
    ("Fertig, ab sofort druckt", "Fertig. Ab sofort druckt"),
    ("Online-Bestellen, ideal während", "Online-Bestellen. Ideal während"),
    ("Zahlung erhalten, willkommen!", "Zahlung erhalten. Willkommen!"),
    ("+ (d.inhaber || '') + ', hier finden", "+ (d.inhaber || '') + '. Hier finden"),
    ("E-Mail, Stripe, API-Keys, alles auf", "E-Mail, Stripe, API-Keys. Alles auf"),
    ("(SSH), bleibt lokal", "(SSH). Bleibt lokal"),
    ("an SHY001“ , Jarvis nutzt", "an SHY001“. Jarvis nutzt"),
    ("an SHY001\", Jarvis nutzt", "an SHY001\". Jarvis nutzt"),
    ("eingefügt, User, Passwort und Absender", "eingefügt. User, Passwort und Absender"),
    ("wählen, rechts erscheinen", "wählen. Rechts erscheinen"),
    ("Willkommen bei Webschmiede, Ihr System", "Willkommen bei Webschmiede. Ihr System"),
    ("Tab <strong>Bestellungen</strong>, neue", "Tab <strong>Bestellungen</strong>: neue"),
    ("Tab <strong>Speisekarte</strong>, Preise", "Tab <strong>Speisekarte</strong>: Preise"),
    ("Tab <strong>Aktionen</strong>, Rabatte", "Tab <strong>Aktionen</strong>: Rabatte"),
    ("Tab <strong>Kunden</strong>, CRM", "Tab <strong>Kunden</strong>: CRM"),
    ("Position, hier eintragen", "Position. Hier eintragen"),
    ("<em>, Falls du USt", "<em>Falls du USt"),
    ("Lieferportalen, Wartung oft", "Lieferportalen. Wartung oft"),
    (", ideal fürs Catering", ". Ideal fürs Catering"),
    (", hausgemacht'", ". Hausgemacht'"),
    ("Jedes Gericht, so wie ich", "Jedes Gericht so, wie ich"),
    ("schreiben, dann richten wir", "schreiben. Dann richten wir"),
    ("| `dist-backup/` , Snapshot", "| `dist-backup/` · Snapshot"),
    ("`dist-backup/` , Snapshot", "`dist-backup/` · Snapshot"),
    # Global Agency select
    (f'">, Global (Agency), </option>', f'">{EN} Global (Agency) {EN}</option>'),
    (f"\">, Global (Agency), </option>", f'\">{EN} Global (Agency) {EN}</option>'),
    (f"', Global (Agency), '", f"'{EN} Global (Agency) {EN}'"),
    (f"<option value=\"\">, Global (Agency), </option>", f'<option value="">{EN} Global (Agency) {EN}</option>'),
    (f"innerHTML = '<option value=\"\">, Global (Agency), </option>'",
     f"innerHTML = '<option value=\"\">{EN} Global (Agency) {EN}</option>'"),
]


def fix(text: str) -> str:
    # 1) Platzhalter '—' / "—" / >—< → En-Dash
    text = text.replace(f"'{EM}'", f"'{EN}'")
    text = text.replace(f'"{EM}"', f'"{EN}"')
    text = text.replace(f">{EM}<", f">{EN}<")
    text = text.replace(f">{EM}</", f">{EN}</")
    text = re.sub(rf">\s*{EM}\s*<", f">{EN}<", text)

    # 2) Restliche Em-Dashes → Komma
    text = re.sub(rf"\s*{EM}\s*", ", ", text)

    # 3) Nachkorrekturen
    for a, b in POST:
        text = text.replace(a, b)

    # 4) id — name in option templates oft: `SHY001, Name` aus `SHY001 — Name`
    text = re.sub(
        r"(\$\{(?:esc\()?k\.id(?:\))?})\s*,\s*(\$\{(?:esc\()?k\.name(?:\))?})",
        r"\1 · \2",
        text,
    )
    return text


def main() -> None:
    for rel in FILES:
        p = ROOT / rel
        if not p.exists():
            print("MISSING", rel)
            continue
        raw = p.read_text(encoding="utf-8")
        before = raw.count(EM)
        if before == 0:
            print("ok", rel)
            continue
        new = fix(raw)
        after = new.count(EM)
        p.write_text(new, encoding="utf-8")
        print(f"fixed {rel}: {before} -> {after}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Alle HTML-Verträge: Orange/Weiß-Header, Logo aus assets/, Arial."""
from __future__ import annotations

import base64
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "docs" / "agency" / "vertraege"
ASSETS = DIR / "assets"
LOGO_SRC = ROOT / "app" / "static" / "ci" / "webschmiede-logo.png"
LOGO_FLAT = ASSETS / "webschmiede-logo-print.png"

ASSETS.mkdir(parents=True, exist_ok=True)

# Ensure flat logo exists
from PIL import Image

logo = Image.open(LOGO_SRC).convert("RGBA")
base = Image.new("RGBA", logo.size, (255, 255, 255, 255))
Image.alpha_composite(base, logo).convert("RGB").save(LOGO_FLAT)
shutil.copy(LOGO_FLAT, ASSETS / "webschmiede-logo.png")

b64 = base64.b64encode(LOGO_FLAT.read_bytes()).decode("ascii")
LOGO_IMG = f'<img class="logo" src="data:image/png;base64,{b64}" alt="Webschmiede">'

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: Arial, Helvetica, sans-serif;
  font-size: 10pt;
  color: #1A1A1A;
  background: #eee;
  line-height: 1.45;
}
.page {
  max-width: 210mm;
  margin: 16px auto;
  background: #fff;
  padding: 0 0 18mm;
}
@media print {
  body { background: #fff; }
  .page { margin: 0; box-shadow: none; }
  .no-print { display: none !important; }
  h2, .box, .sig, table, .keep-together {
    break-inside: avoid;
    page-break-inside: avoid;
  }
  .sig { break-before: avoid-page; page-break-before: avoid; }
  ol, ul { break-inside: avoid; page-break-inside: avoid; }
  p { orphans: 3; widows: 3; }
}
.top {
  background: #fff;
  padding: 14px 16mm 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 3px solid #FF6600;
}
.logo-card {
  background: transparent;
  padding: 0;
  display: inline-flex;
  align-items: center;
}
.logo { height: 40px; width: auto; display: block; }
.top-title { color: #1A1A1A; text-align: right; }
.top-title h1 {
  font-family: Arial, Helvetica, sans-serif;
  font-size: 14pt;
  font-weight: 700;
  color: #1A1A1A;
  margin: 0;
}
.top-title p { color: #555; font-size: 8.5pt; margin-top: 4px; }
.content { padding: 14px 16mm 0; }
h2 {
  font-family: Arial, Helvetica, sans-serif;
  font-size: 10pt;
  font-weight: 700;
  margin: 16px 0 8px;
  padding: 7px 10px;
  background: #FF6600;
  color: #fff;
}
.muted { color: #666; font-size: 8.5pt; margin-bottom: 10px; }
.box {
  border: 1px solid #FF6600;
  background: #FFF4ED;
  padding: 12px 14px;
  margin: 8px 0 12px;
}
.ph {
  background: #fff;
  border-bottom: 2px solid #FF6600;
  padding: 0 3px;
}
ul { margin: 6px 0 10px 18px; }
li { margin-bottom: 4px; }
p { margin-bottom: 8px; }
.print-btn {
  position: fixed; bottom: 16px; right: 16px;
  background: #FF6600; color: #fff; border: 0;
  padding: 12px 18px; font-weight: 700; cursor: pointer;
  font-family: Arial, Helvetica, sans-serif;
}
.sig {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 28px;
  margin-top: 28px;
}
.sig .line {
  border-top: 2px solid #FF6600;
  margin-top: 52px;
  padding-top: 6px;
  font-size: 8.5pt;
  color: #666;
}
.foot {
  margin-top: 24px;
  background: #FF6600;
  color: #fff;
  padding: 8px 16mm;
  font-size: 8pt;
}
table { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 10pt; }
th { background: #FF6600; color: #fff; text-align: left; padding: 8px 10px; }
td { padding: 8px 10px; border-bottom: 1px solid #eee; vertical-align: top; }
td.num { text-align: right; white-space: nowrap; }
.total { text-align: right; font-size: 13pt; font-weight: 700; color: #FF6600; margin-top: 10px; }
.meta { margin: 8px 0 4px; font-size: 9.5pt; }
"""


def wrap(title: str, subtitle: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <title>{title} · Webschmiede</title>
  <style>{CSS}</style>
</head>
<body>
<button class="print-btn no-print" onclick="window.print()">Als PDF speichern</button>
<div class="page">
  <div class="top">
    <div class="logo-card">{LOGO_IMG}</div>
    <div class="top-title">
      <h1>{title}</h1>
      <p>{subtitle}</p>
    </div>
  </div>
  <div class="content">
{body}
  </div>
  <div class="foot">Webschmiede · Digitale Handwerkskunst · Meinertzhagener Str. 16 · 53894 Mechernich · Orange &amp; Weiss</div>
</div>
</body>
</html>
"""


angebot_body = """
  <p class="meta">Nr. <span class="ph">AN-2026-___</span> · Datum <span class="ph">TT.MM.JJJJ</span> · Gültig bis <span class="ph">TT.MM.JJJJ</span></p>
  <h2>Kunde</h2>
  <div class="box">
    Firma: <span class="ph">________________</span><br>
    Vertreter: <span class="ph">________________</span> · Funktion: <span class="ph">______</span><br>
    Straße: <span class="ph">________________</span><br>
    PLZ Ort: <span class="ph">________________</span><br>
    E-Mail: <span class="ph">________________</span> · Telefon: <span class="ph">________________</span><br>
    USt-IdNr.: <span class="ph">________________</span>
  </div>
  <h2>Leistung</h2>
  <table>
    <thead><tr><th>Pos.</th><th>Beschreibung</th><th class="num">Betrag netto</th></tr></thead>
    <tbody>
      <tr>
        <td>1</td>
        <td><strong>Setup</strong><br>Paket: <span class="ph">Gastro Bestell-System</span><br>
        Enthalten: <span class="ph">Bestellseite, Admin, Hosting DE</span></td>
        <td class="num"><span class="ph">998,00 €</span></td>
      </tr>
      <tr>
        <td>2</td>
        <td><strong>Monatlicher Betrieb</strong><br>Laufzeit <span class="ph">12</span> Monate, danach <span class="ph">1</span> Monat Frist</td>
        <td class="num"><span class="ph">298,00 € / Monat</span></td>
      </tr>
    </tbody>
  </table>
  <p class="total">Setup netto: <span class="ph">998,00 €</span><br>Monat netto: <span class="ph">298,00 €</span><br>
  <span class="muted" style="font-weight:400;">zzgl. USt. · Fremdkosten separat</span></p>
  <p class="muted">Verbindlich mit Auftrag + AGB. Bei Personendaten zusätzlich AVV.</p>
  <div class="sig">
    <div><div class="line">Ort, Datum · Unterschrift Kunde</div></div>
    <div><div class="line">Ort, Datum · Christian Kummetat · Webschmiede</div></div>
  </div>
"""

auftrag_body = """
  <p class="meta">Digital Services &amp; Automation · Nr. <span class="ph">AU-2026-___</span> · Stand Juli 2026</p>

  <p><strong>Zwischen</strong></p>
  <div class="box">
    <strong>Dienstleister</strong><br>
    Christian Kummetat, Webschmiede – digitale Handwerkskunst<br>
    Meinertzhagener Str. 16, 53894 Mechernich · USt-IdNr. DE370109681
  </div>
  <div class="box">
    <strong>Auftraggeber</strong><br>
    <span class="ph">Firma</span> · <span class="ph">Adresse</span> · Vertreter: <span class="ph">Name</span>
  </div>

  <h2>§ 1 Vertragsgegenstand &amp; Leistungsumfang</h2>
  <ol>
    <li>Digitale Infrastruktur, Automatisierung (n8n, KI, Backend) und digitale Entwicklung.</li>
    <li>Umfang, Meilensteine, Spezifikationen aus Einzelangebot/Lastenheft <span class="ph">AN-2026-___</span> (<strong>Anlage 1</strong>).</li>
    <li>Leistung nach Stand der Technik mit hoher fachlicher Sorgfalt.</li>
  </ol>

  <h2>§ 2 Mitwirkungspflichten</h2>
  <p>Zugänge, API-Schlüssel, Datenstrukturen und Freigaben unverzüglich bereitstellen. Verzögerungen durch fehlende Zuarbeit verschieben Deadlines.</p>

  <h2>§ 3 Vergütung</h2>
  <p>Festpreise pro Meilenstein oder Stundensatz nach Angebot. Zahlung innerhalb <span class="ph">14</span> Tagen. Bei Verzug: Pause laufender Automatisierungs-/Entwicklungsarbeiten.</p>

  <h2>§ 4 Nutzungsrechte</h2>
  <p>Nach Bezahlung Nutzungsrecht an Skripten, Automatisierungen, Workflows. Frameworks/Standard-Module bleiben beim Dienstleister.</p>

  <h2>§ 5 Haftung &amp; Systemverfügbarkeit</h2>
  <p>Unbeschränkt bei Vorsatz/grober Fahrlässigkeit/Personenschäden. Kardinalpflichten begrenzt. Keine Haftung für Drittanbieter-APIs, Hosting oder Dritt-Updates.</p>

  <h2>§ 6 Vertraulichkeit &amp; Datenschutz</h2>
  <p>Geschäftsgeheimnisse, Zugangsdaten, technische Abläufe vertraulich. Bei Personendaten: <strong>AVV</strong> nach DSGVO.</p>

  <h2>§ 7 Laufzeit &amp; Kündigung</h2>
  <p>Inkraft mit Unterzeichnung. Fortlaufende Wartung: Kündigung mit <span class="ph">30</span> Tagen Frist. Fristlose Kündigung aus wichtigem Grund vorbehalten.</p>

  <h2>§ 8 Schlussbestimmungen</h2>
  <p>Textform (E-Mail/Signatur). Salvatorisch. Deutsches Recht, Gerichtsstand Mechernich.</p>

  <div class="sig">
    <div><div class="line">Ort, Datum · Unterschrift Auftraggeber</div></div>
    <div><div class="line">Ort, Datum · Christian Kummetat · Dienstleister</div></div>
  </div>
"""

agb_body = """
  <p class="muted">Nur gegenüber Unternehmern (§ 14 BGB) · Stand Juli 2026</p>
  <p class="meta">Kunde: <span class="ph">________________</span> · Auftrag: <span class="ph">AU-2026-___</span></p>
  <h2>Bedingungen</h2>
  <ol style="margin-left:18px;">
    <li>Geltung nur B2B. Abweichungen nur mit ausdrücklicher Zustimmung.</li>
    <li>Leistung nach Angebot/Auftrag. Keine Umsatz-/Ranking-/Anrufzahl-Garantie.</li>
    <li>Kunde liefert rechtmäßige Inhalte und Zugänge. Endkunden-Datenschutz und Impressum bleiben beim Kunden.
    Der Kunde stellt den Auftragnehmer von Ansprüchen Dritter frei, die aus Kundeninhalten oder Weisungen entstehen, soweit gesetzlich zulässig.</li>
    <li>Preise netto + USt. Fremdkosten nach Angebot. Verzug: Aussetzung nach Mahnung möglich.
    Preisanpassung nach Ankündigung (mind. 6 Wochen) möglich; bei Erhöhung &gt;5 % hat der Kunde ein Sonderkündigungsrecht zum Wirksamkeitsdatum.</li>
    <li>Nutzungsrecht an der Kundeninstanz für die Laufzeit. Frameworks/Templates bleiben bei Webschmiede.
    Kundendaten und vom Kunden gelieferte Texte/Assets bleiben beim Kunden.</li>
    <li>Keine 100 %-Verfügbarkeit. Ausfälle oder Fehler von Drittanbieter-APIs (z. B. Meta, Stripe, Twilio, SMS)
    außerhalb des Einflussbereichs des Auftragnehmers begründen keine Haftung, soweit gesetzlich zulässig.</li>
    <li>Mängel unverzüglich melden. Nacherfüllung in angemessener Frist. Schlägt Nacherfüllung fehl: Minderung
    oder Kündigung der betroffenen Leistung. Gewährleistung im Übrigen nach AGB/Haftung.</li>
    <li>Haftung unbeschränkt bei Vorsatz, grober Fahrlässigkeit und Personenschäden. Leichte Fahrlässigkeit nur bei
    Kardinalpflichten, begrenzt auf den vorhersehbaren Schaden, höchstens Nettovergütung der letzten 12 Monate.
    Keine Haftung für indirekte Schäden, entgangenen Gewinn oder Datenverlust, soweit gesetzlich zulässig und
    zumutbare Backups/Mitwirkung möglich waren.</li>
    <li>Personendaten: AVV. Geschäftsgeheimnisse vertraulich für die Laufzeit und 3 Jahre danach;
    Ausnahmen: gesetzliche Pflichten, öffentlich bekannte Informationen.</li>
    <li>Bei Ende/Betriebsende: Datenexport soweit möglich. Kein Anspruch auf Fortführung darüber hinaus.</li>
    <li>Referenznennung (Name/Logo) ok ohne Widerspruch. Deutsches Recht. Gerichtsstand soweit zulässig: Sitz Auftragnehmer.</li>
  </ol>
  <div class="sig">
    <div><div class="line">Ort, Datum · Unterschrift Auftraggeber</div></div>
    <div><div class="line">Ort, Datum · Christian Kummetat · Webschmiede</div></div>
  </div>
"""

avv_body = """
  <p class="meta">Nr. <span class="ph">AVV-2026-___</span> · Art. 28 Abs. 3 DSGVO · Stand Juli 2026 · 99,8 % Standard</p>

  <p><strong>Zwischen</strong></p>
  <div class="box">
    <strong>Verantwortlicher (Kunde)</strong><br>
    <span class="ph">Firmenname des Kunden</span><br>
    Vertreten durch: <span class="ph">Name Geschäftsführer / Inhaber</span><br>
    <span class="ph">Straße, PLZ Ort</span><br>
    E-Mail Datenschutz: <span class="ph">________________</span>
  </div>
  <div class="box">
    <strong>Auftragsverarbeiter</strong><br>
    Christian Kummetat, handelnd unter „Webschmiede – digitale Handwerkskunst“<br>
    Meinertzhagener Str. 16, 53894 Mechernich · info@digitalehandwerkskunst.de · USt-IdNr. DE370109681
  </div>

  <h2>§ 1 Gegenstand, Dauer und Spezifikation der Verarbeitung</h2>
  <ol>
    <li><strong>Gegenstand:</strong> Leistungen im Rahmen des Hauptvertrages (Managed Services, n8n-Automation, CRM, Messaging/APIs). Leistungen: <span class="ph">n8n-Automation, Portal, CRM, Hosting, KI-Workflows soweit gebucht</span></li>
    <li><strong>Dauer:</strong> Entspricht der Laufzeit des Hauptvertrages.</li>
    <li><strong>Art und Zweck:</strong> Erhebung, Speicherung, Anpassung, Auslesen, Verknüpfung und Löschung im Rahmen der Automatisierungs-Pipelines.</li>
    <li><strong>Betroffene:</strong> <span class="ph">Kunden, Leads, Ansprechpartner, Mitarbeiter</span></li>
    <li><strong>Datenarten:</strong> <span class="ph">Kontaktdaten, Kommunikationsinhalte, Metadaten, Stammdaten</span></li>
  </ol>

  <h2>§ 2 Pflichten und Weisungsgebundenheit</h2>
  <p>Verarbeitung nur auf dokumentierte Weisung (Hauptvertrag, AVV, Textform). Hinweis bei rechtswidriger Weisung.</p>

  <h2>§ 3 Vertraulichkeit und Personal</h2>
  <p>Vertraulichkeitsverpflichtung aller Betrauten; gilt auch nach Vertragsende.</p>

  <h2>§ 4 Datensicherheit &amp; TOMs</h2>
  <p>Maßnahmen gemäß Art. 32 DSGVO; Details in <strong>Anlage 1</strong>. Anpassung möglich ohne Absenkung des Schutzniveaus.</p>

  <h2>§ 5 Subunternehmer &amp; KI-APIs</h2>
  <p>Allgemeine Genehmigung für Subunternehmer (<strong>Anlage 2</strong>). <strong>14-Tage-Fiktionsklausel</strong> bei Änderungen (Textform). KI nur über Enterprise-APIs mit No-Training/Zero-Retention-SLA.</p>

  <h2>§ 6 Rechte der Betroffenen</h2>
  <p>Unterstützung bei Art. 12–22 und Art. 32–36 DSGVO, soweit zumutbar.</p>

  <h2>§ 7 Audits und Kontrollrechte</h2>
  <p>Nachweise primär über Zertifikate (z. B. ISO 27001 Hetzner). Vor-Ort-Audit nach Ankündigung, ohne Störung und ohne Gefährdung anderer Mandanten.</p>

  <h2>§ 8 Löschung und Rückgabe</h2>
  <p>Löschung oder Rückgabe <strong>binnen 30 Tagen</strong> nach Vertragsende bzw. Weisung (Backup-Rotation längstens weitere 30 Tage), soweit keine gesetzliche Speicherpflicht. n8n-Logs: automatisches Pruning nach 7–14 Tagen (<code>EXECUTIONS_DATA_PRUNE=true</code>).</p>

  <h2>§ 9 Schlussbestimmungen</h2>
  <p>Salvatorische Klausel. Deutsches Recht.</p>

  <h2>Anlage 1: TOMs</h2>
  <ul>
    <li><strong>Zutrittskontrolle:</strong> Hetzner DE, ISO 27001</li>
    <li><strong>Zugangskontrolle:</strong> SSH-Keys, 2FA, Passwort-Manager</li>
    <li><strong>Zugriffskontrolle:</strong> RBAC, Docker-Mandantentrennung</li>
    <li><strong>Integrität:</strong> TLS 1.3, Encryption at Rest, N8N_ENCRYPTION_KEY</li>
    <li><strong>Verfügbarkeit:</strong> Nächtliche Backups DE, Disaster Recovery</li>
    <li><strong>Überprüfung:</strong> Security-Updates, Log-Pruning, KI-Transparenz (lokal vs. EU-API)</li>
  </ul>

  <h2>Anlage 2: Genehmigte Subunternehmer</h2>
  <table>
    <tr><th>Unternehmen</th><th>Funktion</th><th>Standort</th><th>Grundlage</th></tr>
    <tr><td>Hetzner Online GmbH</td><td>Hosting</td><td>DE (Nürnberg)</td><td>Art. 28 AVV</td></tr>
    <tr><td>DocuSeal (self-hosted)</td><td>E-Signatur</td><td>DE/Hetzner</td><td>Art. 28 AVV</td></tr>
    <tr><td>Meta Platforms Ireland</td><td>WhatsApp Business API</td><td>EU</td><td>SCCs/DPF</td></tr>
    <tr><td>OpenAI Ireland (optional)</td><td>KI-API</td><td>EU/USA</td><td>DPA, DPF</td></tr>
    <tr><td>Requesty B.V. (optional)</td><td>LLM-Gateway</td><td>EU</td><td>Art. 28, No-Training</td></tr>
    <tr><td>seven.io, Stripe, Cloudflare, Cal.com</td><td>soweit gebucht</td><td>DE/EU/SCC</td><td>Art. 28/SCC</td></tr>
  </table>
  <p class="muted">Weitere Anbieter nur nach § 5 (14-Tage-Fiktionsklausel).</p>

  <div class="sig">
    <div><div class="line">Ort, Datum · Verantwortlicher (Kunde)</div></div>
    <div><div class="line">Ort, Datum · Webschmiede – digitale Handwerkskunst</div></div>
  </div>
"""

datenschutz_body = """
  <h2>Wer ist wofür zuständig?</h2>
  <p><strong>Du</strong> bleibst für die Daten deiner Gäste, Anrufer und Mitarbeiter verantwortlich.</p>
  <p><strong>Wir</strong> betreiben die Technik (Auftragsverarbeiter). Dafür unterschreiben wir den AVV.</p>
  <h2>Was wir typischerweise verarbeiten</h2>
  <ul>
    <li>Bestell- und Kontaktdaten aus dem Portal</li>
    <li>Telefonnummern und Nachrichten (SMS / WhatsApp), wenn gebucht</li>
    <li>Anruf-Metadaten bei Voice, wenn gebucht</li>
    <li>Technische Logs</li>
  </ul>
  <h2>Was du selbst erledigen musst</h2>
  <ul>
    <li>Impressum und Datenschutzhinweis</li>
    <li>Rechtsgrundlage gegenüber Endkunden</li>
    <li>Auskunfts- und Löschanfragen (wir helfen technisch)</li>
  </ul>
"""

files = {
    "01-angebot.html": ("Angebot", "B2B · freibleibend bis Auftragsbestätigung", angebot_body),
    "02-auftrag-dienstleistungsvertrag.html": (
        "Dienstleistungsvertrag Digital Services & Automation",
        "Webschmiede · B2B",
        auftrag_body,
    ),
    "03-agb-b2b.html": ("AGB B2B", "Stand Juli 2026 · nur Unternehmer", agb_body),
    "04-avv-auftragsverarbeitung.html": ("AVV Art. 28 DSGVO", "Auftragsverarbeitung", avv_body),
    "05-datenschutz-kundenhinweis.html": ("Datenschutz, kurz erklärt", "Für Gewerbekunden der Webschmiede", datenschutz_body),
}

for name, (title, sub, body) in files.items():
    (DIR / name).write_text(wrap(title, sub, body), encoding="utf-8")
    print("wrote", name)

print("Logo assets:", LOGO_FLAT)

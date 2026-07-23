#!/usr/bin/env python3
"""
Webschmiede Vertragspaket → DocuSeal-Vorlagen (self-host).

- Liest DOCUSEAL_* vom Web-Server (nicht lokal nötig)
- Legt/aktualisiert Vorlagen via POST /api/templates/html (external_id)
- Optional: Test-Signatur an AGENCY_OWNER_EMAIL

Usage:
  python scripts/upload_vertraege_docuseal.py
  python scripts/upload_vertraege_docuseal.py --test-mail
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paramiko
from agency_config import ssh_connect

FOLDER = "Webschmiede Verträge"
ROLE_K = "Kunde"
ROLE_W = "Webschmiede"

# Standard-Beispiel aus angebote.json (Gastro · Bestell-System)
DEFAULT_PAKET = "Gastro · Bestell-System"
DEFAULT_SETUP = "998,00 €"
DEFAULT_MONAT = "298,00 € / Monat"
DEFAULT_FEATURES = (
    "Website mobil & schnell; Speisekarte; Google Maps; "
    "eigene Bestellseite (/bestellen); Admin für Küche; "
    "Zu/Auf + Wartezeit; Hosting in Deutschland"
)
DEFAULT_NOT = "Druck, Ads-Budget, Rechtsberatung, SMS-Kontingent (nach Verbrauch)"


def f_text(
    name: str,
    role: str = ROLE_K,
    w: int = 200,
    h: int = 18,
    default: str = "",
    required: bool = True,
    readonly: bool = False,
) -> str:
    attrs = [
        f'name="{name}"',
        f'role="{role}"',
        f'required="{"true" if required else "false"}"',
        f'style="width: {w}px; height: {h}px; display: inline-block; margin-bottom: -3px; '
        f'border-bottom: 1px solid #ccc;"',
    ]
    if default:
        attrs.append(f'default="{default}"')
    if readonly:
        attrs.append('readonly="true"')
    return "<text-field " + " ".join(attrs) + "></text-field>"


def f_date(name: str, role: str, w: int = 110) -> str:
    return (
        f'<date-field name="{name}" role="{role}" required="true" '
        f'style="width: {w}px; height: 18px; display: inline-block; margin-bottom: -3px;"></date-field>'
    )


def f_sig(name: str, role: str) -> str:
    return (
        f'<signature-field name="{name}" role="{role}" required="true" '
        f'style="width: 220px; height: 70px; display: inline-block; '
        f'border: 1px dashed #bbb;"></signature-field>'
    )


CSS = """
body { font-family: DejaVu Sans, Arial, sans-serif; font-size: 11px; color: #1a1a1a; line-height: 1.4; }
h1 { font-size: 18px; margin: 0 0 4px; }
h2 { font-size: 13px; margin: 14px 0 6px; border-bottom: 1px solid #e8e4dc; padding-bottom: 3px; }
.muted { color: #666; font-size: 10px; }
.bar { height: 4px; background: #C9A84C; margin-bottom: 12px; }
.box { border: 1px solid #e8e4dc; background: #faf8f4; padding: 10px 12px; margin: 8px 0; border-radius: 4px; }
table { width: 100%; border-collapse: collapse; margin: 8px 0; }
th { background: #1a1712; color: #e8c76a; text-align: left; padding: 6px 8px; font-size: 10px; }
td { padding: 6px 8px; border-bottom: 1px solid #eee; vertical-align: top; }
.num { text-align: right; white-space: nowrap; }
ul { margin: 4px 0 8px 16px; padding: 0; }
.siggrid { width: 100%; margin-top: 20px; }
.siggrid td { width: 50%; vertical-align: top; border: 0; padding: 8px 12px 0 0; }
.small { font-size: 9px; color: #555; }
"""


def wrap(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"><title>{title}</title>
<style>{CSS}</style></head><body>
<div class="bar"></div>
{body}
</body></html>"""


def html_angebot() -> str:
    body = f"""
<h1>Angebot</h1>
<p class="muted">Webschmiede · Digitale Handwerkskunst · Christian Kummetat<br>
Meinertzhagener Str. 16 · 53894 Mechernich · info@digitalehandwerkskunst.de · 0177 8011350<br>
USt-IdNr. DE370109681 · nur B2B</p>

<p>Nr. {f_text("Angebotsnummer", ROLE_W, 120, default="AN-2026-", required=True)}
&nbsp; Datum {f_date("Angebotsdatum", ROLE_W)}
&nbsp; Gültig bis {f_date("Gueltig bis", ROLE_W)}</p>

<div class="box">
<strong>Angebot für</strong><br>
Firma: {f_text("Firma", ROLE_K, 280)}<br>
Vertreten durch: {f_text("Vertreter", ROLE_K, 220)}
Funktion: {f_text("Funktion", ROLE_K, 120, required=False)}<br>
Straße: {f_text("Strasse", ROLE_K, 280)}<br>
PLZ Ort: {f_text("PLZ Ort", ROLE_K, 200)}<br>
E-Mail: {f_text("Email", ROLE_K, 220)}
Telefon: {f_text("Telefon", ROLE_K, 140)}<br>
USt-IdNr.: {f_text("USt-Id", ROLE_K, 160, required=False)}
</div>

<div class="box">
Branche: {f_text("Branche", ROLE_W, 160, default="Gastro", required=False)}
Ziel: {f_text("Ziel", ROLE_W, 260, default="Online-Bestellen", required=False)}
</div>

<h2>Leistung</h2>
<table>
<tr><th>Pos.</th><th>Beschreibung</th><th class="num">Betrag netto</th></tr>
<tr>
  <td>1</td>
  <td><strong>Setup / Einrichtung</strong><br>
  Paket: {f_text("Paket", ROLE_W, 260, default=DEFAULT_PAKET)}<br>
  Enthalten: {f_text("Enthalten", ROLE_W, 400, h=36, default=DEFAULT_FEATURES)}<br>
  Nicht enthalten: {f_text("Nicht enthalten", ROLE_W, 360, default=DEFAULT_NOT, required=False)}
  </td>
  <td class="num">{f_text("Setup Preis", ROLE_W, 90, default=DEFAULT_SETUP)}</td>
</tr>
<tr>
  <td>2</td>
  <td><strong>Monatlicher Betrieb</strong> (ab Go-Live)<br>
  Hosting/Betrieb, Support im Rahmen, Updates nach Absprache<br>
  Laufzeit: {f_text("Laufzeit", ROLE_W, 80, default="12 Monate")} ,
  danach kündbar mit {f_text("Kuendigungsfrist", ROLE_W, 70, default="1 Monat")} Frist
  </td>
  <td class="num">{f_text("Monat Preis", ROLE_W, 110, default=DEFAULT_MONAT)}</td>
</tr>
</table>

<p><strong>Setup gesamt netto:</strong> {f_text("Setup Summe", ROLE_W, 90, default=DEFAULT_SETUP)}<br>
<strong>Monat netto:</strong> {f_text("Monat Summe", ROLE_W, 110, default=DEFAULT_MONAT)}<br>
<span class="muted">zzgl. gesetzlicher Umsatzsteuer · Fremdkosten (SMS, Voice, Domains) separat</span></p>

<h2>Wichtig</h2>
<ul>
<li>Nur Gewerbetreibende (B2B).</li>
<li>Verbindlich mit unterschriebenem Auftrag und AGB.</li>
<li>Bei personenbezogenen Daten zusätzlich AVV.</li>
<li>Angebot freibleibend bis zur Auftragsbestätigung.</li>
</ul>

<table class="siggrid"><tr>
<td>
  Ort/Datum Kunde {f_date("Datum Kunde Angebot", ROLE_K)}<br>
  {f_sig("Unterschrift Kunde Angebot", ROLE_K)}<br>
  <span class="small">Annahme Angebot (optional)</span>
</td>
<td>
  Ort/Datum Webschmiede {f_date("Datum Webschmiede Angebot", ROLE_W)}<br>
  {f_sig("Unterschrift Webschmiede Angebot", ROLE_W)}<br>
  <span class="small">Christian Kummetat</span>
</td>
</tr></table>
"""
    return wrap("Angebot Webschmiede", body)


def html_auftrag() -> str:
    path = ROOT / "docs" / "agency" / "vertraege" / "docuseal" / "02-auftrag.html"
    return path.read_text(encoding="utf-8")


def html_agb() -> str:
    body = f"""
<h1>Allgemeine Geschäftsbedingungen (B2B)</h1>
<p class="muted">Webschmiede · Christian Kummetat · Digitale Handwerkskunst · Stand: Juli 2026<br>
Nur gegenüber Unternehmern (§ 14 BGB).</p>

<p class="small">Kunde: {f_text("Firma", ROLE_K, 240, required=False)} ·
Auftrag: {f_text("Auftragsnummer Ref", ROLE_W, 120, default="AU-2026-", required=False)}</p>

<h2>1. Geltung</h2>
<p>Diese AGB gelten für digitale Dienstleistungen, Software-Nutzung, Hosting, Automation,
Messaging und Voice. Abweichende Bedingungen des Auftraggebers nur bei ausdrücklicher Zustimmung.</p>

<h2>2. Leistungen</h2>
<p>Umfang aus Angebot und Auftrag. Keine Erfolgsgarantie (Umsatz, Ranking, Anrufzahlen),
sofern nicht schriftlich vereinbart.</p>

<h2>3. Mitwirkung, Zugänge, Inhalte</h2>
<ul>
<li>Auftraggeber liefert korrekte, rechtmäßige Inhalte und Zugänge.</li>
<li>Auftraggeber bleibt für Angebote, Preise, Impressum und Datenschutz gegenüber Endkunden verantwortlich.</li>
<li>API-Keys nur so weit speichern wie nötig; nicht an Dritte außer erforderliche Dienstleister (AVV).</li>
<li>Der Auftraggeber stellt den Auftragnehmer von Ansprüchen Dritter frei, die aus Kundeninhalten
oder Weisungen des Auftraggebers entstehen, soweit gesetzlich zulässig.</li>
</ul>

<h2>4. Vergütung, Fremdkosten, Preisanpassung</h2>
<p>Preise netto zzgl. USt. Fremdkosten Dritter trägt der Auftraggeber nach Angebot/Freigabe.
Bei Verzug: Aussetzung nach Mahnung und Fristsetzung möglich.
Preisanpassung nach Ankündigung (mindestens 6 Wochen) möglich. Bei Erhöhung um mehr als 5 %
hat der Auftraggeber ein Sonderkündigungsrecht zum Wirksamkeitsdatum der Anpassung.</p>

<h2>5. Nutzungsrechte</h2>
<p>Templates/Frameworks bleiben beim Auftragnehmer. Einfaches Nutzungsrecht an der Kundeninstanz
für die Vertragslaufzeit. Kundendaten und vom Kunden gelieferte Texte/Assets bleiben beim Auftraggeber.</p>

<h2>6. Verfügbarkeit und Drittanbieter</h2>
<p>Wartung und Störungen bei Dritten (Hosting, Meta, Twilio, Retell, SMS, Zahlungsanbieter) können
die Verfügbarkeit beeinflussen. Keine 100-Prozent-Garantie. Wesentliche Änderungen werden mitgeteilt.
Keine Haftung für Ausfälle oder fehlerhafte Daten von Drittanbieter-APIs außerhalb des Einflussbereichs
des Auftragnehmers, soweit gesetzlich zulässig.</p>

<h2>7. Mängel</h2>
<p>Mängel unverzüglich melden. Der Auftragnehmer leistet Nacherfüllung in angemessener Frist.
Schlägt die Nacherfüllung fehl, kann der Auftraggeber die betroffene Leistung mindern oder kündigen.
Weitergehende Ansprüche richten sich nach Ziffer 8.</p>

<h2>8. Haftung</h2>
<ul>
<li>Unbeschränkt bei Vorsatz, grober Fahrlässigkeit und bei Verletzung von Leben, Körper, Gesundheit.</li>
<li>Leichte Fahrlässigkeit nur bei Kardinalpflichten, begrenzt auf den vorhersehbaren Schaden,
höchstens die Nettovergütung der letzten 12 Monate vor dem Schadenfall.</li>
<li>Keine Haftung für indirekte Schäden, entgangenen Gewinn oder Datenverlust, soweit gesetzlich zulässig
und zumutbare Backups/Mitwirkung möglich waren.</li>
</ul>

<h2>9. Datenschutz, Geheimhaltung</h2>
<p>Personenbezogene Daten: AVV. Geschäftsgeheimnisse vertraulich für die Vertragslaufzeit und drei Jahre
danach. Ausnahmen: gesetzliche Pflichten und Informationen, die ohne Verstoß öffentlich bekannt sind.</p>

<h2>10. Vertragsende, Daten, Betriebsende</h2>
<ul>
<li>Bei Beendigung: Export kundeneigener Daten in zumutbarer Frist.</li>
<li>Hosting und Zugänge dürfen danach enden. Domain/DNS-Umzug und Backups liegen beim Auftraggeber.</li>
<li>Bei Einstellung des Betriebs oder Insolvenz des Auftragnehmers: Datenherausgabe soweit möglich und zulässig;
kein Anspruch auf Fortführung darüber hinaus.</li>
</ul>

<h2>11. Referenz</h2>
<p>Referenznennung (Name/Logo) erlaubt, sofern der Auftraggeber nicht widerspricht.</p>

<h2>12. Schluss</h2>
<p>Deutsches Recht. Gerichtsstand, soweit zulässig: Sitz des Auftragnehmers. Salvatorische Klausel.</p>

<p><strong>Bestätigung:</strong> Mit Unterschrift gelten diese AGB für den genannten Auftrag.</p>

<table class="siggrid"><tr>
<td>
  {f_date("Datum Kunde AGB", ROLE_K)}<br>
  {f_sig("Unterschrift Kunde AGB", ROLE_K)}<br>
  <span class="small">Auftraggeber</span>
</td>
<td>
  {f_date("Datum Webschmiede AGB", ROLE_W)}<br>
  {f_sig("Unterschrift Webschmiede AGB", ROLE_W)}<br>
  <span class="small">Christian Kummetat</span>
</td>
</tr></table>
"""
    return wrap("AGB B2B Webschmiede", body)


def html_avv() -> str:
    path = ROOT / "docs" / "agency" / "vertraege" / "docuseal" / "04-avv.html"
    return path.read_text(encoding="utf-8")


TEMPLATES = [
    {
        "external_id": "ws-angebot",
        "name": "WS Angebot",
        "html": html_angebot,
        "shared_link": True,
    },
    {
        "external_id": "ws-auftrag",
        "name": "WS Auftrag Dienstleistung",
        "html": html_auftrag,
        "shared_link": True,
    },
    {
        "external_id": "ws-agb",
        "name": "WS AGB B2B",
        "html": html_agb,
        "shared_link": True,
    },
    {
        "external_id": "ws-avv",
        "name": "WS AVV Auftragsverarbeitung",
        "html": html_avv,
        "shared_link": True,
    },
]


def remote_secrets() -> dict[str, str]:
    """Token nur im Speicher, nie printen."""
    remote = r"""
python3 - <<'PY'
from pathlib import Path
import re, json
vals = {}
for p in [Path('/root/app/deploy.secrets.local'), Path('/root/app/backend/.env')]:
    if not p.exists():
        continue
    for ln in p.read_text(encoding='utf-8', errors='replace').splitlines():
        if not ln.strip() or ln.strip().startswith('#') or '=' not in ln:
            continue
        k, v = ln.split('=', 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k in ('DOCUSEAL_URL', 'DOCUSEAL_API_TOKEN', 'AGENCY_OWNER_EMAIL', 'AGENCY_SMTP_FROM') and v:
            vals.setdefault(k, v)
print(json.dumps(vals))
PY
"""
    c = paramiko.SSHClient()
    ssh_connect(c, timeout=25, banner_timeout=25, role="web")
    try:
        _, o, e = c.exec_command(remote, timeout=40)
        out = o.read().decode("utf-8", "replace").strip()
        err = e.read().decode("utf-8", "replace").strip()
        if err and not out:
            raise RuntimeError(err[:300])
        # last JSON line
        line = [ln for ln in out.splitlines() if ln.startswith("{")][-1]
        data = json.loads(line)
    finally:
        c.close()
    if not data.get("DOCUSEAL_API_TOKEN"):
        raise RuntimeError("DOCUSEAL_API_TOKEN fehlt auf dem Server")
    return data


def api_base(url: str) -> str:
    base = (url or "https://sign.digitalehandwerkskunst.de").strip().rstrip("/")
    if "api.docuseal." in base:
        return base
    return base


def request_json(method: str, url: str, token: str, body: dict | None = None) -> dict | list:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "X-Auth-Token": token,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read().decode("utf-8", "replace") or "{}"
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"HTTP {e.code} {url}: {err_body}") from e


def upsert_template(base: str, token: str, tpl: dict) -> dict:
    payload = {
        "name": tpl["name"],
        "html": tpl["html"](),
        "size": "A4",
        "external_id": tpl["external_id"],
        "folder_name": FOLDER,
        "shared_link": bool(tpl.get("shared_link", True)),
    }
    # multi-doc Kundenstart
    if tpl.get("documents"):
        payload.pop("html", None)
        payload["documents"] = [
            {"name": d["name"], "html": d["html"]()} for d in tpl["documents"]
        ]
    return request_json("POST", f"{base}/api/templates/html", token, payload)


def upsert_kundenstart(base: str, token: str) -> dict:
    payload = {
        "name": "WS Kundenstart (Auftrag+AGB+AVV)",
        "size": "A4",
        "external_id": "ws-kundenstart",
        "folder_name": FOLDER,
        "shared_link": True,
        "documents": [
            {"name": "01 Auftrag", "html": html_auftrag()},
            {"name": "02 AGB", "html": html_agb()},
            {"name": "03 AVV", "html": html_avv()},
        ],
    }
    return request_json("POST", f"{base}/api/templates/html", token, payload)


def send_test(base: str, token: str, template_id: int, email: str) -> dict:
    payload = {
        "template_id": template_id,
        "send_email": True,
        "order": "preserved",
        "message": {
            "subject": "Test: Webschmiede Vertrag unterschreiben",
            "body": (
                "Christian, das ist der automatische Test vom Vertrags-Paket. "
                "Bitte einmal als Kunde und danach als Webschmiede durchklicken. "
                "Wenn das klappt, bist du startklar."
            ),
        },
        "submitters": [
            {
                "role": ROLE_K,
                "email": email,
                "name": "Test Kunde (Christian)",
            },
            {
                "role": ROLE_W,
                "email": email,
                "name": "Christian Kummetat",
            },
        ],
    }
    return request_json("POST", f"{base}/api/submissions", token, payload)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-mail", action="store_true", help="Test-Signatur an Owner-Mail")
    ap.add_argument("--save-html", action="store_true", help="HTML lokal nach docs/agency/vertraege/docuseal speichern")
    args = ap.parse_args()

    out_dir = ROOT / "docs" / "agency" / "vertraege" / "docuseal"
    if args.save_html or True:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "01-angebot.html").write_text(html_angebot(), encoding="utf-8")
        (out_dir / "02-auftrag.html").write_text(html_auftrag(), encoding="utf-8")
        (out_dir / "03-agb.html").write_text(html_agb(), encoding="utf-8")
        (out_dir / "04-avv.html").write_text(html_avv(), encoding="utf-8")
        print(f"HTML gespeichert: {out_dir}")

    print("Secrets vom Server holen …")
    sec = remote_secrets()
    token = sec["DOCUSEAL_API_TOKEN"]
    base = api_base(sec.get("DOCUSEAL_URL") or "https://sign.digitalehandwerkskunst.de")
    owner = (sec.get("AGENCY_OWNER_EMAIL") or sec.get("AGENCY_SMTP_FROM") or "").strip()
    print(f"DocuSeal: {base}")
    print(f"Test-Mail Ziel: {'gesetzt' if owner else 'FEHLT'}")

    results = []
    for tpl in TEMPLATES:
        print(f"Upload {tpl['name']} …")
        res = upsert_template(base, token, tpl)
        tid = res.get("id")
        slug = res.get("slug")
        print(f"  OK id={tid} slug={slug}")
        results.append(res)

    print("Upload WS Kundenstart …")
    ks = upsert_kundenstart(base, token)
    print(f"  OK id={ks.get('id')} slug={ks.get('slug')}")
    results.append(ks)

    listed = request_json("GET", f"{base}/api/templates", token)
    n = len(listed) if isinstance(listed, list) else len(listed.get("data") or [])
    print(f"Vorlagen gesamt auf DocuSeal: {n}")

    if args.test_mail:
        if not owner:
            print("Keine Owner-Mail, Test übersprungen")
            return 1
        tid = ks.get("id")
        if not tid:
            print("Kein Kundenstart-Template-ID")
            return 1
        print(f"Sende Test-Submission (template {tid}) …")
        sub = send_test(base, token, int(tid), owner)
        # don't dump emails/tokens; show ids only
        if isinstance(sub, list):
            print(f"  Submission(s): {len(sub)}")
            for s in sub[:3]:
                print(f"  id={s.get('id')} status={s.get('status')}")
        elif isinstance(sub, dict):
            print(f"  id={sub.get('id')} status={sub.get('status')}")
            if "submitters" in sub:
                print(f"  submitters={len(sub.get('submitters') or [])}")
        else:
            print("  Antwort OK")

    # write short status without secrets
    status = {
        "folder": FOLDER,
        "templates": [
            {
                "external_id": t.get("external_id"),
                "name": t.get("name"),
                "id": t.get("id"),
                "slug": t.get("slug"),
            }
            for t in results
        ],
        "dashboard": f"{base}/templates",
    }
    status_path = ROOT / "docs" / "agency" / "vertraege" / "docuseal-status.json"
    status_path.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Status: {status_path}")
    print("Fertig.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Angebot PDF: Multiunternehmer Oak Office / Care 4 You (+ 3. Firma)
Preise aus kalkulator-preise.json (Firma 1 / High-End), Stand 22.07.2026.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "agency" / "angebote"
ASSETS = ROOT / "docs" / "agency" / "vertraege" / "assets"
LOGO_SRC = ROOT / "app" / "static" / "ci" / "webschmiede-logo.png"
LOGO_FLAT = ASSETS / "webschmiede-logo-print.png"

OUT_DIR.mkdir(parents=True, exist_ok=True)
ASSETS.mkdir(parents=True, exist_ok=True)

W, H = A4
ML = 18 * mm
MR = 18 * mm
CONTENT_W = W - ML - MR

ORANGE = HexColor("#FF6600")
ORANGE_SOFT = HexColor("#FFF4ED")
INK = HexColor("#1A1A1A")
MUTED = HexColor("#555555")
LINE = HexColor("#E5E5E5")
PAPER = HexColor("#FAFAFA")

_FONT = "Helvetica"
_FONT_B = "Helvetica-Bold"


def _register_arial() -> None:
    global _FONT, _FONT_B
    candidates = [
        (Path(r"C:\Windows\Fonts\arial.ttf"), Path(r"C:\Windows\Fonts\arialbd.ttf")),
        (
            Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
            Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
        ),
    ]
    for regular, bold in candidates:
        if regular.exists() and bold.exists():
            pdfmetrics.registerFont(TTFont("ArialWS", str(regular)))
            pdfmetrics.registerFont(TTFont("ArialWS-Bold", str(bold)))
            _FONT, _FONT_B = "ArialWS", "ArialWS-Bold"
            return


def _prepare_logo() -> Path:
    if LOGO_FLAT.exists():
        return LOGO_FLAT
    logo = PILImage.open(LOGO_SRC).convert("RGBA")
    base = PILImage.new("RGBA", logo.size, (255, 255, 255, 255))
    flat = PILImage.alpha_composite(base, logo).convert("RGB")
    flat.save(LOGO_FLAT, "PNG")
    return LOGO_FLAT


def draw_logo(c: canvas.Canvas, x: float, y: float, height: float) -> float:
    path = _prepare_logo()
    width = height * (1114 / 268)
    c.drawImage(str(path), x, y, width=width, height=height, preserveAspectRatio=True, mask="auto")
    return width


def wrap(text: str, width: int = 92) -> list[str]:
    return textwrap.wrap(text, width=width) or [""]


def euro(n: float) -> str:
    s = f"{n:,.0f}".replace(",", ".")
    return f"{s} €"


_register_arial()


class Doc:
    def __init__(self, path: Path):
        self.path = path
        self.c = canvas.Canvas(str(path), pagesize=A4)
        self.y = H - 16 * mm
        self.page = 1

    def new_page(self) -> None:
        self._footer()
        self.c.showPage()
        self.page += 1
        self.y = H - 16 * mm
        self._header_small()

    def _footer(self) -> None:
        self.c.setStrokeColor(LINE)
        self.c.setLineWidth(0.5)
        self.c.line(ML, 12 * mm, W - MR, 12 * mm)
        self.c.setFont(_FONT, 7.5)
        self.c.setFillColor(MUTED)
        self.c.drawString(ML, 7 * mm, "Webschmiede · digitalehandwerkskunst.de · Alle Preise netto zzgl. USt.")
        self.c.drawRightString(W - MR, 7 * mm, f"Seite {self.page}")

    def _header_small(self) -> None:
        draw_logo(self.c, ML, H - 14 * mm, 7 * mm)
        self.c.setFont(_FONT, 8)
        self.c.setFillColor(MUTED)
        self.c.drawRightString(W - MR, H - 11 * mm, "AN-2026-OAK-001 · Angebot")
        self.c.setStrokeColor(LINE)
        self.c.line(ML, H - 16 * mm, W - MR, H - 16 * mm)
        self.y = H - 22 * mm

    def ensure(self, need: float) -> None:
        if self.y - need < 22 * mm:
            self.new_page()

    def h1(self, text: str) -> None:
        self.ensure(14 * mm)
        self.c.setFont(_FONT_B, 16)
        self.c.setFillColor(INK)
        self.c.drawString(ML, self.y, text)
        self.y -= 8 * mm

    def h2(self, text: str) -> None:
        self.ensure(12 * mm)
        self.y -= 2 * mm
        self.c.setFillColor(ORANGE)
        self.c.rect(ML, self.y - 1 * mm, 2.2 * mm, 5.5 * mm, fill=1, stroke=0)
        self.c.setFont(_FONT_B, 11)
        self.c.setFillColor(INK)
        self.c.drawString(ML + 5 * mm, self.y, text)
        self.y -= 7 * mm

    def p(self, text: str, size: float = 9, color=INK, leading: float = 4.2 * mm) -> None:
        for line in wrap(text, 98):
            self.ensure(leading + 2)
            self.c.setFont(_FONT, size)
            self.c.setFillColor(color)
            self.c.drawString(ML, self.y, line)
            self.y -= leading

    def bullet(self, text: str) -> None:
        for i, line in enumerate(wrap(text, 94)):
            self.ensure(4.2 * mm)
            self.c.setFont(_FONT, 9)
            self.c.setFillColor(INK)
            prefix = "•  " if i == 0 else "   "
            self.c.drawString(ML + 2 * mm, self.y, prefix + line)
            self.y -= 4.2 * mm

    def spacer(self, mm_h: float = 3) -> None:
        self.y -= mm_h * mm

    def price_row(self, label: str, einmalig: str, monatlich: str, bold: bool = False) -> None:
        self.ensure(6 * mm)
        font = _FONT_B if bold else _FONT
        self.c.setFont(font, 8.5 if not bold else 9)
        self.c.setFillColor(INK)
        self.c.drawString(ML, self.y, label[:62])
        self.c.drawRightString(ML + CONTENT_W * 0.72, self.y, einmalig)
        self.c.drawRightString(W - MR, self.y, monatlich)
        self.y -= 5 * mm

    def table_header(self) -> None:
        self.ensure(8 * mm)
        self.c.setFillColor(ORANGE_SOFT)
        self.c.roundRect(ML, self.y - 2.5 * mm, CONTENT_W, 7 * mm, 2, fill=1, stroke=0)
        self.c.setFont(_FONT_B, 8)
        self.c.setFillColor(INK)
        self.c.drawString(ML + 2 * mm, self.y, "Leistung")
        self.c.drawRightString(ML + CONTENT_W * 0.72, self.y, "Einmalig")
        self.c.drawRightString(W - MR - 2 * mm, self.y, "Monatlich")
        self.y -= 7 * mm

    def box(self, title: str, lines: list[str], accent: bool = False) -> None:
        body = []
        for t in lines:
            body.extend(wrap(t, 90))
        h = 7 * mm + len(body) * 4 * mm + 3 * mm
        self.ensure(h + 2)
        bg = ORANGE_SOFT if accent else PAPER
        self.c.setFillColor(bg)
        self.c.setStrokeColor(ORANGE if accent else LINE)
        self.c.setLineWidth(0.8 if accent else 0.5)
        self.c.roundRect(ML, self.y - h + 3 * mm, CONTENT_W, h, 3, fill=1, stroke=1)
        self.c.setFont(_FONT_B, 9)
        self.c.setFillColor(ORANGE if accent else INK)
        self.c.drawString(ML + 3 * mm, self.y - 1.5 * mm, title)
        yy = self.y - 6.5 * mm
        self.c.setFont(_FONT, 8.5)
        self.c.setFillColor(INK)
        for line in body:
            self.c.drawString(ML + 3 * mm, yy, line)
            yy -= 4 * mm
        self.y -= h + 2 * mm

    def finish(self) -> None:
        self._footer()
        self.c.save()


def build() -> Path:
    out = OUT_DIR / "AN-2026-OAK-001_Multiunternehmer_Oak-Care4You.pdf"
    d = Doc(out)

    # --- Deckblatt-Header ---
    draw_logo(d.c, ML, H - 22 * mm, 11 * mm)
    d.c.setFont(_FONT, 8)
    d.c.setFillColor(MUTED)
    d.c.drawRightString(W - MR, H - 14 * mm, "digitalehandwerkskunst.de")
    d.c.drawRightString(W - MR, H - 18 * mm, "info@digitalehandwerkskunst.de")
    d.y = H - 28 * mm

    d.c.setFillColor(ORANGE)
    d.c.rect(ML, d.y, CONTENT_W, 0.8 * mm, fill=1, stroke=0)
    d.y -= 10 * mm

    d.c.setFont(_FONT_B, 8)
    d.c.setFillColor(ORANGE)
    d.c.drawString(ML, d.y, "ANGEBOT  ·  AN-2026-OAK-001")
    d.y -= 7 * mm

    d.c.setFont(_FONT_B, 18)
    d.c.setFillColor(INK)
    d.c.drawString(ML, d.y, "Meta-Werbung, Lead-Pipeline")
    d.y -= 7 * mm
    d.c.drawString(ML, d.y, "& Multi-Firmen-Dashboard")
    d.y -= 8 * mm

    d.p(
        "Für Oak Office, Care 4 You Assistenz und eine dritte Firma unter einem Dach — "
        "zuerst Büros voll bekommen, danach Personal finden, parallel Kundendaten und "
        "Pipeline sauber auf deutschen Servern.",
        size=9.5,
        color=MUTED,
        leading=4.5 * mm,
    )
    d.spacer(3)

    # Meta
    d.c.setFont(_FONT, 8.5)
    d.c.setFillColor(MUTED)
    meta = [
        ("Angebotsdatum", "22. Juli 2026"),
        ("Gültig bis", "21. August 2026"),
        ("Empfänger", "Multiunternehmer · Oak Office / Care 4 You Assistenz (+ 3. Firma)"),
        ("Bezug", "oakoffice.de · care4youassistenz.de"),
        ("Hosting / Recht", "Server in Deutschland · AVV · DSGVO-orientierte Prozesse"),
    ]
    for k, v in meta:
        d.ensure(5 * mm)
        d.c.setFont(_FONT_B, 8)
        d.c.setFillColor(MUTED)
        d.c.drawString(ML, d.y, k)
        d.c.setFont(_FONT, 8.5)
        d.c.setFillColor(INK)
        d.c.drawString(ML + 38 * mm, d.y, v)
        d.y -= 4.8 * mm

    d.spacer(4)
    d.h2("Ausgangslage")
    d.p(
        "Drei Firmen, ein Unternehmer. Phase 1: Oak Office über Meta-Werbung füllen "
        "(Virtual Office / Business / Private Office). Phase 2: Recruiting-Ads für "
        "Assistenzkräfte (Care 4 You). Parallel gewünscht: eigenes Dashboard mit "
        "Kundendaten, Lead-Pipeline und Automatisierungen — getrennt je Firma, "
        "Hosting in DE, AVV und dokumentierte Verarbeitung."
    )
    d.bullet("Keine US-CRM-Blackbox als Kern — System unter Ihrer Kontrolle.")
    d.bullet("Ad-Spend (Media-Budget) läuft über Ihr Meta-Konto und ist nicht in den Honoraren enthalten.")
    d.bullet("Dritte Firma im Angebot als Option vorgesehen; Name bei Auftragsklärung.")

    d.spacer(2)
    d.h2("Empfohlener Fahrplan")
    d.bullet("Phase A (sofort): Meta für Oak Office — Setup, Tracking, Kampagnen, laufende Optimierung.")
    d.bullet("Phase B (direkt danach oder parallel): Dashboard + Pipeline für Firma 1 (Oak), Server DE, AVV.")
    d.bullet("Phase C: weitere Firmen anbinden; Recruiting-Ads Care 4 You, wenn Kapazität steht.")

    # ========== OPTIONEN ==========
    d.new_page()
    d.h1("Leistungsoptionen & Preise")
    d.p(
        "Alle Beträge netto, zzgl. gesetzlicher USt. Kalkulation nach Webschmiede-Preisliste "
        "Firma 1 (High-End). Retainer: 6 Monate −5 %, 12 Monate −10 %."
    )

    # Option 1
    d.h2("Option 1 — Nur Meta für Oak Office (Einstieg)")
    d.p("Ziel: Büros / Adressen verkaufen. Website bleibt oakoffice.de; wir schärfen Tracking und Conversion.")
    d.table_header()
    d.price_row("Ads-Setup (Business Manager, Pixel/Events, Kampagnenstruktur, Launch)", euro(1000), "—")
    d.price_row("Texte & Creatives-Konzept (Anzeigen-Copy, Varianten, Briefing Grafik)", euro(1200), "—")
    d.price_row("Conversion-Feinschliff oakoffice.de (Formulare, CTAs, Event-Tracking)", euro(900), "—")
    d.price_row("Ads-Management & Optimierung (Reporting, A/B, Budgetsteuerung)", "—", euro(1200))
    d.price_row("Zwischensumme Setup", euro(3100), "—", bold=True)
    d.price_row("Retainer ab Monat 1", "—", euro(1200), bold=True)
    d.spacer(1)
    d.box(
        "Media-Budget (nicht im Honorar)",
        [
            "Empfehlung Start: 2.000–4.000 € / Monat über Ihr Meta-Konto.",
            "Wird von Meta abgerechnet — Webschmiede stellt nur die Steuerung in Rechnung.",
        ],
    )
    d.box(
        "Beispiel 3 Monate Option 1",
        [
            f"Setup {euro(3100)} + 3 × {euro(1200)} Retainer = {euro(6700)} netto Honorar.",
            f"Mit Media z. B. 3 × 2.500 € = 7.500 € bei Meta (Ihr Konto).",
            f"Bei 6 Monaten Retainer (−5 %): {euro(1140)}/Mo statt {euro(1200)}.",
        ],
        accent=True,
    )

    # Option 2
    d.h2("Option 2 — Oak Ads + Dashboard / Pipeline (1 Firma)")
    d.p(
        "Alles aus Option 1 plus eigenes System: Leads und Kunden, Pipeline-Stufen, "
        "Basis-Automatisierungen, Login für Sie — Server in Deutschland, AVV."
    )
    d.table_header()
    d.price_row("Alles aus Option 1 (Setup Ads + Conversion)", euro(3100), euro(1200))
    d.price_row("Server DE (Hetzner), Isolation, Backups, Monitoring-Grundlage", euro(1200), euro(300))
    d.price_row("Kern-Setup: Dashboard, CRM-Daten, Lead-Pipeline, Onboarding", euro(3500), "—")
    d.price_row("Automatisierungen n8n (Lead → Pipeline, Notify, Follow-up-Basis)", euro(2200), euro(500))
    d.price_row("Zwischensumme Setup", euro(10000), "—", bold=True)
    d.price_row("Retainer (Ads + Hosting + Automationen)", "—", euro(2000), bold=True)
    d.spacer(1)
    d.box(
        "Beispiel 6 Monate Option 2 (−5 % Retainer)",
        [
            f"Setup {euro(10000)} + 6 × {euro(1900)} = {euro(21400)} netto Honorar.",
            "(1.900 € = 2.000 € × 0,95). Media-Budget weiterhin separat.",
        ],
        accent=True,
    )

    # Option 3
    d.ensure(55 * mm)
    d.h2("Option 3 — Multi-Firmen (bis 3 Mandanten)")
    d.p(
        "Wie Option 2, plus Mandantentrennung und Anbindung Care 4 You sowie der dritten Firma. "
        "Gleiche Oberfläche, getrennte Datenräume, Rollen/Zugriffe."
    )
    d.table_header()
    d.price_row("Basis wie Option 2 (Ads Oak + System Firma 1)", euro(10000), euro(2000))
    d.price_row("Anbindung weitere Firma (je Mandant: Pipeline, Daten, Automationen)", euro(1500) + " × 2", "+ " + euro(400) + " je")
    d.price_row("Zwischensumme Setup (3 Firmen)", euro(13000), "—", bold=True)
    d.price_row("Retainer 3 Firmen (Ads Oak + Hosting + Automationen)", "—", euro(2800), bold=True)
    d.spacer(1)
    d.box(
        "Beispiel 12 Monate Option 3 (−10 % Retainer)",
        [
            f"Setup {euro(13000)} + 12 × {euro(2520)} = {euro(43240)} netto Honorar.",
            "(2.520 € = 2.800 € × 0,90). Recruiting-Ads Care 4 You siehe Optionen unten.",
        ],
        accent=True,
    )

    # ========== ADD-ONS ==========
    d.new_page()
    d.h1("Zusatzoptionen")
    d.h2("Recruiting-Ads Care 4 You (später)")
    d.table_header()
    d.price_row("Kampagnen-Setup Recruiting (Pixel/Events, Stellen-Funnel-Tracking)", euro(1000), "—")
    d.price_row("Copy & Kreativ-Briefing Assistenz-Stellen", euro(800), "—")
    d.price_row("Ads-Management zweites Konto / zweite Zielgruppe", "—", euro(800))
    d.p(
        "Wenn Option 1/2 bereits Ads-Management für Oak enthält: zweites Konto als Aufpreis "
        f"{euro(800)}/Mo statt Vollpreis — oder gebündelt im Multi-Retainer nach Abstimmung."
    )

    d.h2("Weitere Bausteine (nach Bedarf)")
    d.table_header()
    d.price_row("WhatsApp Business / Messaging-Anbindung (Setup)", euro(2200), "im Auto-Retainer")
    d.price_row("KI-Assistent (FAQ, Vorqualifizierung Leads) Setup", euro(3500), "nach Umfang")
    d.price_row("Social Content / Redaktion parallel zu Ads", "—", euro(1200))
    d.price_row("Workshop vor Ort / remote (Konzeption Pipeline, Ziele)", euro(1500) + " / Tag", "—")
    d.price_row("Stundenarbeit außerhalb Retainer", euro(180) + " / Std.", "—")

    d.h2("Was im Dashboard enthalten ist (Phase B/C)")
    d.bullet("Mandantenfähig: Oak, Care 4 You, dritte Firma — getrennte Kundendaten.")
    d.bullet("Lead-Pipeline: Stufen (z. B. Anfrage → Qualifiziert → Angebot → Kunde / Absage).")
    d.bullet("Automatisierungen: Benachrichtigung, Statuswechsel, Erinnerungen (n8n).")
    d.bullet("Hosting DE, Backups, Zugänge; AVV zur Auftragsverarbeitung.")
    d.bullet("Keine Rechtsberatung — DSGVO-Umsetzung mit Ihrem Datenschutzbedarf abgestimmt.")

    d.h2("Nicht enthalten")
    d.bullet("Media-Budget Meta / sonstige Werbenetzwerke.")
    d.bullet("Externe Grafikproduktion (Fotografie, Film) — Koordination möglich.")
    d.bullet("Anwaltliche Prüfung, Steuerberatung, DATEV-Buchhaltung (optional später).")
    d.bullet("Umbau der öffentlichen Websites über den Conversion-Feinschliff hinaus.")

    d.spacer(3)
    d.h2("Empfehlung")
    d.box(
        "Pragmatischer Start",
        [
            "Start mit Option 1 (Meta Oak), parallel Kickoff Option 2 (Dashboard Firma 1).",
            "Sobald Pipeline läuft: Care 4 You + dritte Firma (Option 3-Aufpreis).",
            "Recruiting-Ads erst, wenn Sie Kapazität für neue Assistenzkräfte haben.",
            f"Mindestlaufzeit Ads/Retainer: 3 Monate. Sinnvoll: 6 Monate (−5 %).",
        ],
        accent=True,
    )

    d.h2("Nächste Schritte")
    d.bullet("1. Option wählen (1 / 2 / 3) und gewünschte Laufzeit.")
    d.bullet("2. Name der dritten Firma + Ansprechpartner / Rechnungsadresse.")
    d.bullet("3. Zugang Meta Business Manager Oak Office; AVV unterzeichnen.")
    d.bullet("4. Kickoff (ca. 90 Min.) — Ziele, Kapazität Büros, Zielgruppen, Pipeline-Stufen.")
    d.bullet("5. Termin: cal.digitalehandwerkskunst.de/christian/erstgespraech")

    d.spacer(6)
    d.p("Mit freundlichen Grüßen", size=9)
    d.spacer(2)
    d.c.setFont(_FONT_B, 10)
    d.c.setFillColor(INK)
    d.c.drawString(ML, d.y, "Christian Kummetat")
    d.y -= 4.5 * mm
    d.c.setFont(_FONT, 8.5)
    d.c.setFillColor(MUTED)
    d.c.drawString(ML, d.y, "Webschmiede · Digitale Handwerkskunst")
    d.y -= 8 * mm
    d.p(
        "Dieses Angebot ist freibleibend bis zum Gültigkeitsdatum. Änderungen nach Scope-Klärung "
        "möglich. Es gelten die zum Auftrag vereinbarten AGB / AVV.",
        size=7.5,
        color=MUTED,
        leading=3.5 * mm,
    )

    d.finish()
    return out


if __name__ == "__main__":
    path = build()
    print(path)

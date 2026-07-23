#!/usr/bin/env python3
"""
Vertrag-PDFs: Arial, Orange/Weiß-CI, Logo fest eingebettet (ohne Alpha).
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
OUT = ROOT / "docs" / "agency" / "vertraege" / "pdf"
ASSETS = ROOT / "docs" / "agency" / "vertraege" / "assets"
OUT.mkdir(parents=True, exist_ok=True)
ASSETS.mkdir(parents=True, exist_ok=True)

LOGO_SRC = ROOT / "app" / "static" / "ci" / "webschmiede-logo.png"
LOGO_FLAT = ASSETS / "webschmiede-logo-print.png"

W, H = A4
ML = 18 * mm
MR = 18 * mm
CONTENT_W = W - ML - MR

ORANGE = HexColor("#FF6600")
ORANGE_SOFT = HexColor("#FFF4ED")
INK = HexColor("#1A1A1A")
MUTED = HexColor("#555555")
LINE = HexColor("#E5E5E5")
FIELD_BG = HexColor("#FFFFFF")
FIELD_BORDER = HexColor("#D0D0D0")

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
    """Flatten logo onto white PNG so every viewer shows it. Returns path."""
    if not LOGO_SRC.exists():
        raise FileNotFoundError(LOGO_SRC)
    logo = PILImage.open(LOGO_SRC).convert("RGBA")
    base = PILImage.new("RGBA", logo.size, (255, 255, 255, 255))
    flat = PILImage.alpha_composite(base, logo).convert("RGB")
    flat.save(LOGO_FLAT, "PNG")
    return LOGO_FLAT


def draw_logo(c: canvas.Canvas, x: float, y: float, height: float) -> float:
    path = _prepare_logo()
    # native aspect 1114x268
    width = height * (1114 / 268)
    c.drawImage(str(path), x, y, width=width, height=height, preserveAspectRatio=True, mask="auto")
    return width


_register_arial()


def font(size: float, bold: bool = False):
    return (_FONT_B if bold else _FONT), size


def header(c: canvas.Canvas, title: str, subtitle: str = "") -> float:
    """White top band: logo left, title right in black. Thin orange line under."""
    header_h = 24 * mm
    c.setFillColor(white)
    c.rect(0, H - header_h, W, header_h, fill=1, stroke=0)

    logo_h = 12 * mm
    draw_logo(c, ML, H - header_h + (header_h - logo_h) / 2, logo_h)

    c.setFillColor(INK)
    c.setFont(*font(13, bold=True))
    c.drawRightString(W - MR, H - 10 * mm, title)
    if subtitle:
        c.setFillColor(MUTED)
        c.setFont(*font(7.5))
        c.drawRightString(W - MR, H - 15 * mm, subtitle)

    c.setStrokeColor(ORANGE)
    c.setLineWidth(2.5)
    c.line(0, H - header_h, W, H - header_h)

    y = H - header_h - 8 * mm
    c.setFillColor(INK)
    return y


def footer(c: canvas.Canvas, page: int = 1, pages: int = 1):
    c.setFillColor(ORANGE)
    c.rect(0, 0, W, 8 * mm, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont(*font(7))
    c.drawString(ML, 3 * mm, "Webschmiede · Digitale Handwerkskunst · Orange & Weiss")
    c.drawRightString(W - MR, 3 * mm, f"Seite {page}/{pages}")


def section(c: canvas.Canvas, title: str, y: float) -> float:
    y -= 6
    # Orange section bar with white text
    c.setFillColor(ORANGE)
    c.roundRect(ML, y - 5, CONTENT_W, 17, 2, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont(*font(9.5, bold=True))
    c.drawString(ML + 8, y, title)
    return y - 20


def label(c: canvas.Canvas, text: str, x: float, y: float, size: float = 8):
    c.setFont(*font(size))
    c.setFillColor(MUTED)
    c.drawString(x, y, text)
    c.setFillColor(INK)


def tf(c: canvas.Canvas, name: str, x: float, y: float, w: float = 200, h: float = 14, value: str = ""):
    c.acroForm.textfield(
        name=name,
        tooltip=name,
        x=x,
        y=y,
        width=w,
        height=h,
        borderWidth=0.8,
        borderColor=ORANGE,
        fillColor=FIELD_BG,
        textColor=INK,
        forceBorder=True,
        fontSize=9,
        fontName=FIELD_FONT,
        fieldFlags="",
        value=value,
    )


def sig(c: canvas.Canvas, name: str, x: float, y: float, w: float = 220, h: float = 36):
    c.acroForm.textfield(
        name=name,
        tooltip=name,
        x=x,
        y=y,
        width=w,
        height=h,
        borderWidth=1,
        borderColor=ORANGE,
        fillColor=ORANGE_SOFT,
        textColor=INK,
        forceBorder=True,
        fontSize=8,
        fontName=FIELD_FONT,
        fieldFlags="",
    )


def labeled_field(c, lab, name, x, y, w):
    label(c, lab, x, y)
    tf(c, name, x, y - 15, w)


def inline_field(c, lab, name, y, field_w, label_w=72, x=None) -> float:
    x0 = ML if x is None else x
    label(c, lab, x0, y + 3)
    tf(c, name, x0 + label_w, y - 2, field_w)
    return y - 21


def field_row(c, y, items, gap=14, row_h=30) -> float:
    x = ML
    for lab, name, fw in items:
        labeled_field(c, lab, name, x, y, fw)
        x += fw + gap
    return y - row_h


def body_lines(c, y, lines, size=8, leading=10.5) -> float:
    c.setFont(*font(size))
    c.setFillColor(INK)
    for line in lines:
        c.drawString(ML, y, line)
        y -= leading
    return y


PAGE_BOTTOM = 30 * mm
FIELD_FONT = "Helvetica"  # AcroForm: Helvetica für maximale PDF-Viewer-Kompatibilität


class NumberedCanvas(canvas.Canvas):
    """Korrekte Seitenzahl Seite X/Y nach dem Rendern."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._states: list[dict] = []

    def showPage(self):
        self._states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        self._states.append(dict(self.__dict__))
        total = max(len(self._states), 1)
        for i, state in enumerate(self._states):
            self.__dict__.update(state)
            footer(self, page=i + 1, pages=total)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)


def spacing(y: float, gap: float = 6) -> float:
    return y - gap


def para_block(c, y, text, size=7.5, leading=10, width_chars=96, gap_after=6) -> float:
    lines = textwrap.wrap(text, width=width_chars) or [""]
    need = len(lines) * leading + gap_after
    return para(c, y, text, size=size, leading=leading, width_chars=width_chars), need


def draw_para(c, y, text, **kw) -> float:
    y, _ = para_block(c, y, text, **kw)
    return y - kw.get("gap_after", 6)


def field_row_labels(c, y, fields: list[tuple[str, str, float, float]], row_h: float = 22) -> float:
    """fields: (label, name, x_offset_from_ML, width)"""
    for lab, name, xoff, w in fields:
        label(c, lab, ML + xoff, y + 2)
        tf(c, name, ML + xoff, y - 14, w)
    return y - row_h


def need_page(c, y: float, need: float, page: list[int], title: str, subtitle: str) -> float:
    if y - need >= PAGE_BOTTOM:
        return y
    c.showPage()
    page[0] += 1
    return header(c, title, subtitle)


def section_group(c, y, need, page, title, subtitle, section_title, draw_fn) -> float:
    y = need_page(c, y, need + 26, page, title, subtitle)
    y = section(c, section_title, y)
    return draw_fn(c, y)


def para(c, y, text, size=7.5, leading=9.5, width_chars=98) -> float:
    c.setFont(*font(size))
    c.setFillColor(INK)
    for line in textwrap.wrap(text, width=width_chars):
        c.drawString(ML, y, line)
        y -= leading
    return y


def avv_page(c, page: list[int], title: str, subtitle: str = "") -> float:
    c.showPage()
    page[0] += 1
    return header(c, title, subtitle)


def avv_need_page(c, y: float, need: float, page: list[int], title: str, subtitle: str) -> float:
    if y - need >= PAGE_BOTTOM:
        return y
    return avv_page(c, page, title, subtitle)


def sig_block(c, y, suffix: str = "") -> float:
    y = section(c, "Unterschriften", y)
    col = CONTENT_W / 2 - 8
    dk, uk = f"Datum Kunde{suffix}", f"Unterschrift Kunde{suffix}"
    dw, uw = f"Datum Webschmiede{suffix}", f"Unterschrift Webschmiede{suffix}"
    labeled_field(c, dk, dk, ML, y, 100)
    label(c, uk, ML, y - 34)
    sig(c, uk, ML, y - 74, col - 8, 36)
    rx = ML + CONTENT_W / 2 + 8
    labeled_field(c, dw, dw, rx, y, 100)
    label(c, uw, rx, y - 34)
    sig(c, uw, rx, y - 74, col - 8, 36)
    return y - 90


def angebot():
    path = OUT / "01-angebot.pdf"
    c = NumberedCanvas(str(path), pagesize=A4)
    c.setTitle("Angebot Webschmiede")
    page = [1]
    title, sub = "Angebot", "B2B · freibleibend bis Auftragsbestaetigung"
    y = header(c, title, sub)

    y = field_row(
        c,
        y,
        [("Angebotsnummer", "Angebotsnummer", 105), ("Datum", "Angebotsdatum", 90), ("Gueltig bis", "Gueltig bis", 90)],
        gap=16,
        row_h=32,
    )

    y = section(c, "Kunde", y)
    for lab, name, fw in [
        ("Firma", "Firma", CONTENT_W - 80),
        ("Vertreter", "Vertreter", 200),
        ("Funktion", "Funktion", 150),
        ("Strasse", "Strasse", CONTENT_W - 80),
        ("PLZ Ort", "PLZ Ort", 180),
        ("Email", "Email", 210),
        ("Telefon", "Telefon", 140),
        ("USt-Id", "USt-Id", 150),
    ]:
        y = inline_field(c, lab, name, y, fw)

    y = avv_need_page(c, y, 120, page, title, sub)
    y = section(c, "Leistung", y)
    c.setFont(*font(7.5))
    c.setFillColor(MUTED)
    c.drawString(ML, y, "Beispiel: Gastro Bestell-System · Setup 998 EUR · Monat 298 EUR · 12 Monate")
    y -= 14
    y = inline_field(c, "Paket", "Paket", y, CONTENT_W - 80)
    y = field_row_labels(
        c,
        y,
        [
            ("Setup netto", "Setup Preis", 0, 100),
            ("Monat netto", "Monat Preis", 130, 100),
            ("Laufzeit", "Laufzeit", 260, 90),
            ("Kuendigung", "Kuendigungsfrist", 370, 90),
        ],
    )
    y = inline_field(c, "Enthalten", "Enthalten", y, CONTENT_W - 80)
    y = inline_field(c, "Nicht enthalten", "Nicht enthalten", y, CONTENT_W - 100, label_w=95)
    y = body_lines(
        c,
        y,
        [
            "Verbindlich mit Auftrag und AGB. Bei Personendaten zusaetzlich AVV.",
            "Fremdkosten (SMS, Voice, Domains) separat.",
        ],
        size=8,
    )
    y = avv_need_page(c, y, 95, page, title, "Unterschriften")
    sig_block(c, y - 2)
    c.save()
    print("PDF", path.name)


def auftrag():
    path = OUT / "02-auftrag.pdf"
    c = NumberedCanvas(str(path), pagesize=A4)
    c.setTitle("Dienstleistungsvertrag Digital Services Webschmiede")
    page = [1]
    title = "Digital Services & Automation"
    sub = "Webschmiede · B2B · Stand Juli 2026"

    y = header(c, title, sub)
    c.setFont(*font(10, bold=True))
    c.drawString(ML, y, "Dienstleistungsvertrag for Digital Services & Automation")
    y -= 16
    label(c, "Auftragsnummer", ML, y + 2)
    tf(c, "Auftragsnummer", ML, y - 14, 120, value="AU-2026-")
    label(c, "Datum", ML + 200, y + 2)
    tf(c, "Auftragsdatum", ML + 200, y - 14, 100)
    y -= 26

    y = avv_need_page(c, y, 200, page, title, sub)
    y = section(c, "Parteien", y)
    c.setFont(*font(8, bold=True))
    c.setFillColor(INK)
    c.drawString(ML, y, "Dienstleister")
    y -= 11
    c.setFont(*font(7.5))
    c.setFillColor(MUTED)
    for line in [
        "Christian Kummetat, Webschmiede - digitale Handwerkskunst",
        "Meinertzhagener Str. 16, 53894 Mechernich, Deutschland",
        "info@digitalehandwerkskunst.de · USt-IdNr. DE370109681",
    ]:
        c.drawString(ML, y, line)
        y -= 10
    y -= 6
    c.setFont(*font(8, bold=True))
    c.setFillColor(INK)
    c.drawString(ML, y, "Auftraggeber")
    y -= 14
    y = inline_field(c, "Firma", "Firma", y, CONTENT_W - 80)
    y = inline_field(c, "Adresse", "Adresse", y, CONTENT_W - 80)
    y = field_row_labels(
        c,
        y,
        [("Vertreter", "Vertreter", 0, 200), ("Funktion", "Funktion", 230, 110)],
    )
    y = field_row_labels(
        c,
        y,
        [("Email", "Email", 0, 200), ("Telefon", "Telefon", 230, 110)],
    )
    y = inline_field(c, "USt-Id", "USt-Id", y, 160)

    y = avv_need_page(c, y, 130, page, title, sub)
    y = section(c, "§ 1 Vertragsgegenstand und Leistungsumfang", y)
    y = draw_para(
        c,
        y,
        "1. Gegenstand: Dienstleistungen im Bereich digitaler Infrastruktur, Automatisierung "
        "(u. a. n8n-Workflows, KI-Integrationen, Backend-Systeme) sowie digitaler Entwicklung.",
    )
    y = inline_field(c, "Paket", "Paket", y, CONTENT_W - 80)
    y = draw_para(
        c,
        y,
        "2. Leistungsumfang, Meilensteine, technische Spezifikationen und Schnittstellen aus "
        "Einzelangebot oder Lastenheft (Anlage 1).",
    )
    y = field_row_labels(
        c,
        y,
        [("Angebot Nr.", "Angebotsnummer Ref", 0, 100), ("vom", "Angebot Datum Ref", 130, 100)],
    )
    y = draw_para(c, y, "3. Leistungen nach Stand der Technik mit hoher fachlicher Sorgfalt.")

    y = avv_need_page(c, y, 70, page, title, sub)
    y = section(c, "§ 2 Mitwirkungspflichten des Auftraggebers", y)
    y = draw_para(
        c,
        y,
        "1. Zugänge, API-Schluessel, Datenstrukturen und Freigaben unverzueglich und vollstaendig bereitstellen.",
    )
    y = draw_para(
        c,
        y,
        "2. Fehlende oder fehlerhafte Zuarbeit fuehrt zu angemessener Verschiebung vereinbarter Deadlines.",
    )

    y = avv_need_page(c, y, 100, page, title, sub)
    y = section(c, "§ 3 Verguetung und Zahlungsbedingungen", y)
    y = field_row_labels(
        c,
        y,
        [
            ("Setup", "Setup Preis", 0, 80),
            ("Monat", "Monat Preis", 100, 80),
            ("Start", "Start Monat", 200, 80),
            ("EUR/h", "Stundensatz", 300, 60),
        ],
    )
    y = draw_para(c, y, "1. Festpreise pro Meilenstein oder Aufwand nach vereinbartem Stundensatz (Angebot).")
    y = draw_para(c, y, "2. Betraege in Euro zzgl. USt. Fremdkosten (SMS, Voice, APIs) nach Angebot.")
    label(c, "Zahlungsziel (Tage)", ML, y + 2)
    tf(c, "Zahlungsziel", ML, y - 14, 40, value="14")
    y -= 24
    y = draw_para(
        c,
        y,
        "3. Rechnungen ohne Abzug faellig. Bei Verzug: Pause laufender Automatisierungs-/Entwicklungsarbeiten.",
    )

    y = avv_need_page(c, y, 75, page, title, sub)
    y = section(c, "§ 4 Nutzungsrechte und geistiges Eigentum", y)
    y = draw_para(
        c,
        y,
        "1. Nach Bezahlung einfaches, nicht uebertragbares Nutzungsrecht an Skripten, Automatisierungen "
        "und Workflows des Auftraggebers.",
    )
    y = draw_para(
        c,
        y,
        "2. Frameworks und Standard-Module verbleiben beim Dienstleister, sofern nicht anders vereinbart.",
    )

    y = avv_need_page(c, y, 95, page, title, sub)
    y = section(c, "§ 5 Haftung und Systemverfuegbarkeit", y)
    y = draw_para(c, y, "1. Unbeschraenkte Haftung bei Vorsatz, grober Fahrlaessigkeit und Personenschaeden.")
    y = draw_para(
        c,
        y,
        "2. Leichte Fahrlaessigkeit nur bei Kardinalpflichten, begrenzt auf vorhersehbaren Schaden.",
    )
    y = draw_para(
        c,
        y,
        "3. Keine Haftung fuer Ausfaelle, Datenverluste oder Fehlfunktionen durch Drittanbieter-APIs, "
        "Hosting-Provider oder Software-Updates von Drittsystemen.",
    )

    y = avv_need_page(c, y, 70, page, title, sub)
    y = section(c, "§ 6 Vertraulichkeit und Datenschutz", y)
    y = draw_para(c, y, "1. Geschaeftsgeheimnisse, Zugangsdaten und technische Ablaeufe streng vertraulich.")
    y = draw_para(
        c,
        y,
        "2. Personenbezogene Daten: gesonderter AVV nach DSGVO. Auftraggeber bleibt Verantwortlicher.",
    )

    y = avv_need_page(c, y, 95, page, title, sub)
    y = section(c, "§ 7 Vertragslaufzeit und Kuendigung", y)
    y = draw_para(c, y, "1. Vertrag tritt mit Unterzeichnung in Kraft.")
    label(c, "Mindestlaufzeit (Mon.)", ML, y + 2)
    tf(c, "Laufzeit", ML, y - 14, 40, value="12")
    label(c, "Kuendigungsfrist (Tage)", ML + 200, y + 2)
    tf(c, "Kuendigungsfrist", ML + 200, y - 14, 40, value="30")
    y -= 26
    y = draw_para(
        c,
        y,
        "2. Fortlaufende Betreuung/Wartung: Kuendigung mit vereinbarter Frist zum Monatsende (Textform).",
    )
    y = draw_para(
        c,
        y,
        "3. Fristlose Kuendigung aus wichtigem Grund. Nach Ende: Datenexport; Hosting endet.",
    )

    y = avv_need_page(c, y, 80, page, title, sub)
    y = section(c, "§ 8 Schlussbestimmungen", y)
    y = draw_para(c, y, "1. Aenderungen in Schrift- oder Textform (E-Mail/digitale Signatur).")
    y = draw_para(c, y, "2. Salvatorische Klausel.")
    y = draw_para(c, y, "3. Deutsches Recht. Gerichtsstand: Sitz Dienstleister (Mechernich).")

    y = avv_need_page(c, y, 100, page, title, "Unterschriften")
    sig_block(c, y - 2, suffix=" Auftrag")
    c.save()
    print("PDF", path.name)


def agb():
    path = OUT / "03-agb.pdf"
    c = NumberedCanvas(str(path), pagesize=A4)
    c.setTitle("AGB B2B Webschmiede")
    page = [1]
    title, sub = "AGB B2B", "Stand Juli 2026 · nur Unternehmer"

    y = header(c, title, sub)
    label(c, "Firma", ML, y + 2)
    tf(c, "Firma", ML + 50, y - 14, 200)
    label(c, "Auftrag", ML + 280, y + 2)
    tf(c, "Auftragsnummer Ref", ML + 330, y - 14, 110, value="AU-2026-")
    y -= 28

    y = body_lines(
        c,
        y,
        [
            "1. Geltung nur B2B. Abweichende Bedingungen nur mit ausdruecklicher Zustimmung.",
            "2. Leistung nach Angebot/Auftrag. Keine Umsatz-, Ranking- oder Anrufzahl-Garantie.",
            "3. Kunde liefert rechtmaessige Inhalte/Zugaenge. Endkunden-Datenschutz bleibt beim Kunden.",
            "   Freistellung: Kunde stellt AV von Anspruechen Dritter aus Kundeninhalten/Weisungen frei,",
            "   soweit gesetzlich zulaessig.",
            "4. Preise netto zzgl. USt. Fremdkosten nach Angebot. Verzug: Aussetzung nach Mahnung moeglich.",
            "   Preisanpassung mit mind. 6 Wochen Ankuendigung; bei Erhoehung >5% Sonderkuendigung.",
            "5. Nutzungsrecht Kundeninstanz fuer Laufzeit. Frameworks bleiben Webschmiede.",
            "   Kundendaten und gelieferte Texte/Assets bleiben beim Kunden.",
            "6. Keine 100%-Verfuegbarkeit. Keine Haftung fuer Ausfaelle/Fehler von Drittanbieter-APIs",
            "   (z. B. Meta, Stripe, Twilio, SMS) ausserhalb Einflussbereich, soweit gesetzlich zulaessig.",
        ],
        size=8,
        leading=11,
    )

    y = avv_need_page(c, y, 200, page, title, "Maengel · Haftung · Datenschutz · Schluss")
    y = body_lines(
        c,
        y,
        [
            "7. Maengel unverzueglich melden. Nacherfuellung in angemessener Frist. Bei Fehlschlagen:",
            "   Minderung oder Kuendigung der betroffenen Leistung. Weiteres nach Ziffer 8.",
            "8. Haftung unbeschraenkt bei Vorsatz, grober Fahrlaessigkeit und Personenschaeden.",
            "   Leichte Fahrlaessigkeit nur bei Kardinalpflichten, max. Nettoverguetung letzte 12 Monate.",
            "   Keine Haftung fuer indirekte Schaeden, entgangenen Gewinn oder Datenverlust,",
            "   soweit gesetzlich zulaessig und zumutbare Backups/Mitwirkung moeglich waren.",
            "9. Personendaten: AVV. Geschaeftsgeheimnisse vertraulich fuer Laufzeit + 3 Jahre danach;",
            "   Ausnahmen: gesetzliche Pflichten, oeffentlich bekannte Informationen.",
            "10. Bei Ende/Betriebsende: Datenexport soweit moeglich. Kein Anspruch auf Fortfuehrung.",
            "11. Referenznennung (Name/Logo) erlaubt ohne Widerspruch.",
            "12. Deutsches Recht. Gerichtsstand soweit zulaessig: Sitz Auftragnehmer. Salvatorische Klausel.",
        ],
        size=8,
        leading=11,
    )
    y -= 8
    c.setFont(*font(8))
    c.setFillColor(INK)
    c.drawString(ML, y, "Mit Unterschrift gelten diese AGB fuer den genannten Auftrag.")
    y -= 14
    y = avv_need_page(c, y, 100, page, title, "Unterschriften")
    sig_block(c, y)
    c.save()
    print("PDF", path.name)


def avv():
    path = OUT / "04-avv.pdf"
    c = NumberedCanvas(str(path), pagesize=A4)
    c.setTitle("AVV Webschmiede")
    page = [1]
    title = "AVV Art. 28 DSGVO"
    sub = "Auftragsverarbeitung · 99,8 % Standard · Stand Juli 2026"

    y = header(c, title, sub)
    c.setFont(*font(11, bold=True))
    c.drawString(ML, y, "Auftragsverarbeitungsvertrag (AVV)")
    y -= 14
    label(c, "AVV Nummer", ML, y + 3)
    tf(c, "AVV Nummer", ML + 80, y - 2, 120, value="AVV-2026-")
    y -= 21

    y = section(c, "Parteien", y)
    c.setFont(*font(8, bold=True))
    c.setFillColor(INK)
    c.drawString(ML, y, "Verantwortlicher (Kunde)")
    y -= 12
    y = inline_field(c, "Firma", "Firma", y, CONTENT_W - 80)
    y = inline_field(c, "Vertreter", "Vertreter", y, 220)
    y = inline_field(c, "Adresse", "Adresse", y, CONTENT_W - 80)
    y = inline_field(c, "Email Datenschutz", "Email Datenschutz", y, 240)
    y -= 4
    c.setFont(*font(8, bold=True))
    c.drawString(ML, y, "Auftragsverarbeiter")
    y -= 10
    c.setFont(*font(7.5))
    c.setFillColor(MUTED)
    for line in [
        "Christian Kummetat, Webschmiede - digitale Handwerkskunst",
        "Meinertzhagener Str. 16, 53894 Mechernich, Deutschland",
        "info@digitalehandwerkskunst.de · USt-IdNr. DE370109681",
    ]:
        c.drawString(ML, y, line)
        y -= 9

    y = section(c, "§ 1 Gegenstand, Dauer und Spezifikation", y)
    y = para(
        c,
        y,
        "1. Gegenstand: Der Auftragsverarbeiter erbringt fuer den Verantwortlichen Leistungen im Rahmen des "
        "Hauptvertrages (Dienstleistungsvertrag / Managed Services). Hierbei verarbeitet der Auftragsverarbeiter "
        "personenbezogene Daten im Auftrag und nach Weisung des Verantwortlichen - insbesondere Automatisierung von "
        "Kundenanfragen, Lead-Routing, CRM-Synchronisation und messaging-basierte Kommunikation via n8n/APIs.",
    )
    y -= 2
    y = inline_field(
        c,
        "Leistungen AVV",
        "Leistungen AVV",
        y,
        CONTENT_W - 100,
        label_w=70,
    )
    y = para(c, y, "2. Dauer: Die Dauer dieses Vertrages entspricht der Laufzeit des Hauptvertrages.")
    y = para(
        c,
        y,
        "3. Art und Zweck: Erhebung, Erfassung, Strukturierung, Speicherung, Anpassung, Auslesen, Abfrage, "
        "Verknuepfung und Loeschung von Daten im Rahmen der eingerichteten Automatisierungs-Pipelines.",
    )
    y -= 14
    label(c, "Betroffene", ML, y + 3)
    tf(c, "Betroffene", ML + 70, y - 2, CONTENT_W - 80, value="Kunden, Leads, Ansprechpartner, Mitarbeiter")
    y -= 21
    label(c, "Datenarten", ML, y + 3)
    tf(
        c,
        "Datenarten",
        ML + 70,
        y - 2,
        CONTENT_W - 80,
        value="Kontaktdaten, Kommunikation, Metadaten, Stammdaten",
    )
    y -= 24

    y = avv_need_page(c, y, 80, page, title, sub)
    y = section(c, "§ 2 Pflichten und Weisungsgebundenheit", y)
    for text in [
        "1. Der Auftragsverarbeiter verarbeitet personenbezogene Daten ausschliesslich auf dokumentierte Weisung des "
        "Verantwortlichen. Dies gilt auch fuer Uebermittlungen an ein Drittland oder eine internationale Organisation.",
        "2. Die Weisungen werden anfaenglich durch den Hauptvertrag und diesen AVV konkretisiert. Der Verantwortliche "
        "ist berechtigt, nachtraegliche Weisungen in Textform (z. B. per E-Mail) zu erteilen.",
        "3. Der Auftragsverarbeiter informiert den Verantwortlichen unverzueglich, wenn er der Auffassung ist, dass "
        "eine Weisung gegen die DSGVO oder andere Datenschutzbestimmungen verstoesst.",
    ]:
        y = avv_need_page(c, y, 30, page, title, sub)
        y = para(c, y, text)
        y -= 2

    y = avv_need_page(c, y, 50, page, title, sub)
    y = section(c, "§ 3 Vertraulichkeit und Personal", y)
    y = para(
        c,
        y,
        "1. Der Auftragsverarbeiter sichert zu, dass alle mit der Verarbeitung betrauten Personen zur Vertraulichkeit "
        "verpflichtet wurden oder einer angemessenen gesetzlichen Verschwiegenheitspflicht unterliegen.",
    )
    y = para(c, y, "2. Die Verpflichtung zur Vertraulichkeit besteht auch nach Beendigung des Vertrages fort.")

    y = avv_need_page(c, y, 50, page, title, sub)
    y = section(c, "§ 4 Datensicherheit und TOMs", y)
    for text in [
        "1. Der Auftragsverarbeiter trifft gemaess Art. 32 DSGVO alle erforderlichen technischen und organisatorischen "
        "Massnahmen, um ein dem Risiko angemessenes Schutzniveau zu gewaehrleisten.",
        "2. Die konkreten Massnahmen sind in Anlage 1 geregelt (u. a. TLS/SSL, Zugriffsbeschraenkungen, automatisches "
        "Pruning von n8n-Execution-Logs).",
        "3. Der Auftragsverarbeiter ist berechtigt, die Sicherheitsmassnahmen waehrend der Vertragslaufzeit anzupassen, "
        "sofern das vereinbarte Schutzniveau nicht unterschritten wird.",
    ]:
        y = avv_need_page(c, y, 30, page, title, sub)
        y = para(c, y, text)
        y -= 2

    y = avv_need_page(c, y, 80, page, title, sub)
    y = section(c, "§ 5 Subunternehmer und KI-APIs", y)
    for text in [
        "1. Der Verantwortliche erteilt dem Auftragsverarbeiter die allgemeine Genehmigung, weitere Auftragsverarbeiter "
        "gemaess Art. 28 Abs. 2 DSGVO einzusetzen. Die derzeit genehmigten Subunternehmer sind in Anlage 2 aufgefuehrt.",
        "2. Dynamisches Aenderungsverfahren: Beabsichtigt der Auftragsverarbeiter, weitere Subunternehmer einzubinden "
        "oder bestehende zu ersetzen (z. B. neue KI-Nodes oder Schnittstellen in n8n), informiert er den "
        "Verantwortlichen mindestens 14 Tage vorher in Textform (E-Mail).",
        "3. Der Verantwortliche kann der Aenderung aus wichtigem datenschutzrechtlichem Grund innerhalb von 14 Tagen "
        "widersprechen. Erfolgt kein Widerspruch, gilt die Zustimmung als erteilt.",
        "4. KI-Schnittstellen (APIs): Sofern KI-Dienste eingesetzt werden, nutzt der Auftragsverarbeiter "
        "ausschliesslich Enterprise/API-Schnittstellen mit No-Training-SLA. Sensible Verarbeitung erfolgt vorrangig "
        "lokal oder ueber EU-Enterprise-Gateways.",
    ]:
        y = avv_need_page(c, y, 35, page, title, sub)
        y = para(c, y, text)
        y -= 2

    y = avv_need_page(c, y, 60, page, title, sub)
    y = section(c, "§ 6 Rechte der Betroffenen", y)
    for text in [
        "1. Der Auftragsverarbeiter unterstuetzt den Verantwortlichen bei Antraegen auf Wahrnehmung von "
        "Betroffenenrechten (Art. 12-22 DSGVO), soweit technisch moeglich und zumutbar.",
        "2. Der Auftragsverarbeiter unterstuetzt bei der Einhaltung der Pflichten gemaess Art. 32 bis 36 DSGVO "
        "(Datensicherheit, Meldung von Verletzungen, Datenschutz-Folgenabschaetzungen).",
    ]:
        y = para(c, y, text)
        y -= 2

    y = avv_need_page(c, y, 60, page, title, sub)
    y = section(c, "§ 7 Audits und Kontrollrechte", y)
    for text in [
        "1. Der Auftragsverarbeiter stellt dem Verantwortlichen alle erforderlichen Informationen zum Nachweis der "
        "Einhaltung zur Verfuegung.",
        "2. Nachweise ueber TOMs koennen primaer durch Testate, Berichte oder Zertifikate unabhaengiger Instanzen "
        "erbracht werden (z. B. ISO/IEC 27001 Hetzner Online GmbH).",
        "3. Vor-Ort-Inspektionen sind nach vorheriger schriftlicher Ankuendigung zulaessig, duerfen den Betrieb nicht "
        "unangemessen stoeren und keine Daten anderer Kunden gefaehrden.",
    ]:
        y = avv_need_page(c, y, 30, page, title, sub)
        y = para(c, y, text)
        y -= 2

    y = avv_need_page(c, y, 50, page, title, sub)
    y = section(c, "§ 8 Loeschung und Rueckgabe", y)
    y = para(
        c,
        y,
        "1. Nach Abschluss der Verarbeitungsleistungen oder nach Beendigung des Hauptvertrages loescht der "
        "Auftragsverarbeiter alle personenbezogenen Daten oder gibt sie zurueck – binnen 30 Tagen nach "
        "Vertragsende bzw. schriftlicher Weisung, sofern keine gesetzliche Speicherpflicht besteht. "
        "Backup-Kopien werden mit der ueblichen Backup-Rotation mitgeloescht, laengstens innerhalb weiterer 30 Tage.",
    )
    y = para(
        c,
        y,
        "2. Automatisch erzeugte System-Logs (n8n Execution Logs) werden gemaess Retention-Guidelines nach "
        "spaetestens 7 bis 14 Tagen automatisch bereinigt (EXECUTIONS_DATA_PRUNE=true).",
    )

    y = avv_need_page(c, y, 40, page, title, sub)
    y = section(c, "§ 9 Schlussbestimmungen", y)
    y = para(c, y, "1. Sollten einzelne Teile unwirksam sein, bleibt die Wirksamkeit der uebrigen Bestimmungen unberuehrt.")
    y = para(c, y, "2. Es gilt ausschliesslich deutsches Recht. Anlage zum Dienstleistungsvertrag.")

    y = avv_need_page(c, y, 100, page, title, "Anlage 1: TOMs")
    y = section(c, "Anlage 1: Technische und Organisatorische Massnahmen", y)
    tom_blocks = [
        ("Vertraulichkeit", [
            "Zutrittskontrolle: ISO-27001-zertifizierte Rechenzentren (Hetzner, DE).",
            "Zugangskontrolle: SSH-Keys, 2FA fuer Server- und n8n-Administration, Passwort-Manager.",
            "Zugriffskontrolle: Rollenbasierte Rechte; Mandantentrennung durch dedizierte Docker-Container.",
        ]),
        ("Integritaet", [
            "Weitergabekontrolle: Transportverschluesselung (HTTPS/TLS 1.3) zwischen Webhooks, n8n, DocuSeal und APIs.",
            "Verschluesselung at Rest: Datenbanken und n8n-Credentials (N8N_ENCRYPTION_KEY).",
        ]),
        ("Verfuegbarkeit", [
            "Verfuegbarkeitskontrolle: Automatisierte naechtliche Backups auf verschluesselte Storage-Locations (DE).",
            "Wiederherstellbarkeit: Disaster-Recovery-Routinen fuer Docker-Container und Datenbanken.",
        ]),
        ("Ueberpruefung", [
            "Security-Updates fuer Server-OS, Docker-Engine und n8n.",
            "Automatisiertes Pruning unbenoetigter Ausfuehrungsdaten (max. 7-14 Tage).",
            "KI-Transparenz: Dokumentation lokal (Ollama) vs. EU-Enterprise-API.",
        ]),
    ]
    for block_title, items in tom_blocks:
        y = avv_need_page(c, y, 40, page, title, "Anlage 1: TOMs")
        c.setFont(*font(8, bold=True))
        c.setFillColor(INK)
        c.drawString(ML, y, block_title)
        y -= 10
        for item in items:
            y = avv_need_page(c, y, 15, page, title, "Anlage 1: TOMs")
            y = para(c, y, f"- {item}")
            y -= 1

    y = avv_need_page(c, y, 180, page, title, "Anlage 2: Subunternehmer")
    y = section(c, "Anlage 2: Genehmigte Subunternehmer", y)
    subs = [
        ("Hetzner Online GmbH", "Server-Hosting", "DE (Nuernberg)", "Art. 28 AVV"),
        ("DocuSeal (self-hosted)", "E-Signatur", "DE/Hetzner", "Art. 28 AVV"),
        ("Meta Platforms Ireland", "WhatsApp Business API", "EU", "SCCs/DPF"),
        ("OpenAI Ireland (optional)", "KI-Text via API", "EU/USA", "DPA, DPF"),
        ("Requesty B.V. (optional)", "LLM-Routing", "EU", "Art. 28, No-Training"),
        ("seven.io (optional)", "SMS", "DE", "Art. 28 AVV"),
        ("Stripe (optional)", "Zahlungsabwicklung", "EU/SCC", "SCCs"),
        ("Cloudflare (optional)", "CDN/DNS", "EU", "SCCs"),
        ("Cal.com self-hosted (opt.)", "Terminbuchung", "DE", "Art. 28 AVV"),
    ]
    c.setFont(*font(6.5, bold=True))
    c.drawString(ML, y, "Unternehmen")
    c.drawString(ML + 115, y, "Leistung")
    c.drawString(ML + 250, y, "Standort")
    c.drawString(ML + 330, y, "Grundlage")
    y -= 9
    c.setFont(*font(6.5))
    for name, leistung, ort, grund in subs:
        y = avv_need_page(c, y, 12, page, title, "Anlage 2: Subunternehmer")
        c.drawString(ML, y, name[:28])
        c.drawString(ML + 115, y, leistung[:22])
        c.drawString(ML + 250, y, ort[:14])
        c.drawString(ML + 330, y, grund[:16])
        y -= 9
    y -= 4
    y = para(
        c,
        y,
        "Weitere Anbieter nur nach § 5 Abs. 2-3 (14-Tage-Fiktionsklausel). Stand: Vertragsabschluss.",
        size=7,
    )

    y = avv_need_page(c, y, 110, page, title, "Unterschriften")
    y = section(c, "Unterschriften", y)
    col = CONTENT_W / 2 - 8
    labeled_field(c, "Datum Kunde AVV", "Datum Kunde AVV", ML, y, 100)
    label(c, "Unterschrift Kunde AVV", ML, y - 34)
    sig(c, "Unterschrift Kunde AVV", ML, y - 74, col - 8, 36)
    rx = ML + CONTENT_W / 2 + 8
    labeled_field(c, "Datum Webschmiede AVV", "Datum Webschmiede AVV", rx, y, 100)
    label(c, "Unterschrift Webschmiede AVV", rx, y - 34)
    sig(c, "Unterschrift Webschmiede AVV", rx, y - 74, col - 8, 36)

    c.save()
    print("PDF", path.name)


def main() -> int:
    _prepare_logo()
    print(f"Font: {_FONT}")
    print(f"Logo flat: {LOGO_FLAT} exists={LOGO_FLAT.exists()}")
    angebot()
    auftrag()
    agb()
    avv()
    print("Fertig", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

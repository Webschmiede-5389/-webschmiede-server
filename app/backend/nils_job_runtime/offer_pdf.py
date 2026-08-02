# -*- coding: utf-8 -*-
"""Deterministic offer PDF render (no CRM write). Minimal PDF writer — no reportlab."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def safe_filename(*, offer_number: str, company_name: str) -> str:
    num = re.sub(r"[^\w\-]+", "", (offer_number or "ANG").replace(" ", "-")) or "ANG"
    co = re.sub(r"[^\w\-]+", "-", (company_name or "Unternehmen").strip(), flags=re.UNICODE)
    co = re.sub(r"-{2,}", "-", co).strip("-")[:60] or "Unternehmen"
    return f"{num}_{co}.pdf"


def render_offer_pdf(offer: Any, *, dest: Path) -> Path:
    """Write a simple multi-line text PDF from an OfferHit-like object."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        f"Angebot {getattr(offer, 'offer_number', '')}",
        f"Unternehmen: {getattr(offer, 'company_name', '') or '–'}",
        f"Status: {getattr(offer, 'status', '') or '–'}",
        f"Datum: {str(getattr(offer, 'created_at', '') or '–')[:10]}",
        "",
        "Positionen:",
    ]
    offer_lines = list(getattr(offer, "lines", None) or [])
    if offer_lines:
        for i, ln in enumerate(offer_lines, 1):
            desc = getattr(ln, "description", str(ln))
            qty = getattr(ln, "qty", 1)
            unit = getattr(ln, "unit_price_eur", 0)
            total = getattr(ln, "total_eur", 0)
            lines.append(f"{i}. {desc} — {qty} x {_eur(unit)} = {_eur(total)}")
    else:
        lines.append("(keine Positionen hinterlegt)")
    setup = getattr(offer, "setup_price_eur", None)
    monthly = getattr(offer, "monthly_price_eur", None)
    if setup is not None:
        lines.append(f"Setup: {_eur(float(setup))}")
    if monthly is not None:
        lines.append(f"Monatlich: {_eur(float(monthly))}")
    total_disp = getattr(offer, "total_display_eur", None)
    if total_disp is not None:
        lines.append(f"Gesamt (Anzeige): {_eur(float(total_disp))}")
    lines.append("")
    lines.append("Erstellt automatisch aus CRM-Lesedaten (keine Unterschrift).")

    _write_text_pdf(dest, lines)
    return dest


def _eur(v: float) -> str:
    return f"{v:,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", ".")


def _pdf_escape(s: str) -> str:
    # PDF literal string escape; keep Latin-1-ish by replacing unknowns
    out = []
    for ch in s:
        o = ord(ch)
        if ch in ("\\", "(", ")"):
            out.append("\\" + ch)
        elif o < 32 or o > 126:
            # approximate umlauts etc. as ASCII for Helvetica
            repl = {
                "ä": "ae",
                "ö": "oe",
                "ü": "ue",
                "Ä": "Ae",
                "Ö": "Oe",
                "Ü": "Ue",
                "ß": "ss",
                "€": "EUR",
                "—": "-",
                "–": "-",
            }.get(ch)
            if repl:
                out.append(repl)
            elif o < 256:
                out.append(f"\\{o:03o}")
            else:
                out.append("?")
        else:
            out.append(ch)
    return "".join(out)


def _write_text_pdf(path: Path, lines: list[str]) -> None:
    """Minimal single-page PDF with Helvetica text."""
    y0 = 800
    content_lines = ["BT", "/F1 11 Tf", "14 TL", f"50 {y0} Td"]
    first = True
    for raw in lines[:60]:
        esc = _pdf_escape(raw[:110])
        if first:
            content_lines.append(f"({esc}) Tj")
            first = False
        else:
            content_lines.append("T*")
            content_lines.append(f"({esc}) Tj")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", "replace")

    objs: list[bytes] = []
    objs.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objs.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objs.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
    )
    objs.append(
        f"4 0 obj<< /Length {len(stream)} >>stream\n".encode("ascii")
        + stream
        + b"\nendstream\nendobj\n"
    )
    objs.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objs:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objs) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "ascii"
        )
    )
    path.write_bytes(bytes(out))

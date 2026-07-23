# -*- coding: utf-8 -*-
"""UX- + Fact-Gate: nichts als „fertig“ ohne Fakten- und Visual-/Mobile-Check.

Pflicht vor: Live-Freigabe, „fertig programmiert“, Kunden-Demo-Links.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

GATE_VERSION = "2026-07-20"

# Checkliste (muss im Cursor-Prompt + vor „fertig“ durch)
CHECKLIST = (
    {
        "id": "facts",
        "title": "Fakten",
        "items": (
            "Keine erfundenen Preise, Telefon, Öffnungszeiten, Features",
            "Texte stimmen mit Auftrag/Kunde überein",
            "Impressum/Datenschutz-Links wo Pflicht",
        ),
    },
    {
        "id": "links_buttons",
        "title": "Links & Buttons",
        "items": (
            "Jeder Button hat klares Ziel (Bestellen, Anrufen, WhatsApp, Weiter)",
            "Links gehen wohin sie sagen (kein toter href # nur-zum-Schein)",
            "Primär-CTA sichtbar ohne Scroll auf Mobile",
        ),
    },
    {
        "id": "visual",
        "title": "Design & Abstände",
        "items": (
            "CI: Dunkel + Gold oder Kunden-CI, kein Generic-AI-Look",
            "Lesbare Schrift, Kontrast Text/Hintergrund ok",
            "Abstände konsistent, nichts klebt aneinander, nichts zerschnitten",
            "Bilder nicht verzerrt, Logo scharf",
        ),
    },
    {
        "id": "responsive",
        "title": "Viewport / Geräte",
        "items": (
            "Handy (~390px): Layout bricht sauber, kein Horizontal-Scroll",
            "Tablet/Desktop: sinnvoll, nicht nur aufgeblasen",
            "Touch-Ziele groß genug (Finger, nicht Mini-Text-Links)",
        ),
    },
    {
        "id": "ux_sense",
        "title": "Sinn & Flow",
        "items": (
            "Ein Job pro Screen/Abschnitt klar erkennbar",
            "Gast/Kunde findet den nächsten Schritt ohne Rätsel",
            "Fehlerzustände verständlich (leerer Warenkorb, Offline, …)",
        ),
    },
    {
        "id": "functional",
        "title": "Funktion",
        "items": (
            "Happy Path einmal durchgeklickt (oder Shipcheck + manueller Spotcheck)",
            "Formulare/Bestellung/Login wo vorhanden: Absenden testen",
            "Nach Deploy Live-URL geprüft, nicht nur lokal",
        ),
    },
)


DONE_CLAIM_RE = re.compile(
    r"(?i)\b("
    r"fertig|ready|live|deployed|umgesetzt|programmiert|shipped|"
    r"kannst\s+du\s+anschauen|schau\s+mal\s+hier|hier\s+ist\s+(?:die|das|dein)"
    r")\b"
)


def policy_for_prompt(*, short: bool = False) -> str:
    if short:
        return (
            "UX/FACT-GATE: Bevor du „fertig/live“ sagst: Fakten prüfen, "
            "Buttons/Links, Abstände, Mobile (~390px), sinnvoller Flow. "
            "Sonst ehrlich: was noch fehlt."
        )
    lines = [
        "=== UX- + FACT-GATE (Pflicht vor „fertig“) ===",
        "Nichts als fertig/live verkaufen ohne diese Prüfung.",
        "Optimierung je nach Auftrag: Website, Portal, App-Webview, Tischaufsteller.",
        "Ziel: positive UX für Christian UND Endkunden (z.B. Gast am Smartphone).",
    ]
    for block in CHECKLIST:
        lines.append(f"{block['title']}:")
        for it in block["items"]:
            lines.append(f"  • {it}")
    lines.append(
        "Am Ende der Arbeit: kurzer Gate-Report (was geprüft, was noch offen). "
        "Offenes = nicht „fertig“ nennen."
    )
    lines.append("=== ENDE UX-GATE ===")
    return "\n".join(lines)


def claims_done(text: str) -> bool:
    return bool(DONE_CLAIM_RE.search(text or ""))


def soft_warn_if_done_without_gate(reply: str) -> str:
    """Hängt Hinweis an, wenn fertig behauptet ohne Gate-Wort."""
    t = reply or ""
    if not claims_done(t):
        return t
    low = t.lower()
    if any(x in low for x in ("ux-gate", "fact-gate", "shipcheck", "viewport", "mobile geprüft", "gate:")):
        return t
    return (
        t.rstrip()
        + "\n\n(Gate-Hinweis: Vor echter Freigabe noch Fact+UX-Check: "
        "Links/Buttons, Abstände, Mobile, Flow. Sag „ux check“ oder schick die URL.)"
    )


def scan_html_text(html: str, *, base_url: str = "") -> dict[str, Any]:
    """Leichte Heuristik auf HTML-String (kein Ersatz für Augen/Browser)."""
    h = html or ""
    low = h.lower()
    issues: list[str] = []
    ok: list[str] = []

    if 'name="viewport"' in low or "name='viewport'" in low:
        ok.append("viewport meta")
    else:
        issues.append("Kein viewport-Meta (Mobile riskant)")

    # Buttons / CTAs
    btn_like = len(re.findall(r"<button\b", low)) + len(re.findall(r"role=\"button\"", low))
    a_tags = re.findall(r"<a\b([^>]*)>", h, flags=re.I)
    hrefs = []
    dead = 0
    for attrs in a_tags:
        m = re.search(r"href\s*=\s*[\"']([^\"']*)[\"']", attrs, re.I)
        if not m:
            dead += 1
            continue
        href = (m.group(1) or "").strip()
        hrefs.append(href)
        if href in ("", "#", "javascript:void(0)", "javascript:;") or href.lower().startswith("javascript:"):
            dead += 1
    if btn_like + len(a_tags) == 0:
        issues.append("Keine Links/Buttons gefunden")
    else:
        ok.append(f"Links/Buttons: a={len(a_tags)} button≈{btn_like}")
    if dead:
        issues.append(f"{dead} Links ohne echtes Ziel (#/leer/javascript)")

    # Tiny tap targets hard to detect; warn on very small font declarations
    if re.search(r"font-size\s*:\s*(9|10|11)px", low):
        issues.append("Sehr kleine font-size (9–11px) gefunden – Mobile schwer lesbar")

    # Horizontal overflow hints
    if "overflow-x: hidden" in low or "overflow-x:hidden" in low:
        ok.append("overflow-x oft hidden (kann Scroll-Bugs kaschieren – trotzdem Mobile prüfen)")

    # CI hints for agency pages
    if "#c9a84c" in low or "c9a84c" in low:
        ok.append("Gold-Akzent (#C9A84C) vorhanden")

    # images without alt
    imgs = re.findall(r"<img\b([^>]*)>", h, flags=re.I)
    no_alt = 0
    for attrs in imgs:
        if not re.search(r"\balt\s*=", attrs, re.I):
            no_alt += 1
    if no_alt:
        issues.append(f"{no_alt} Bilder ohne alt")

    score = max(0, 100 - 12 * len(issues))
    ship = len(issues) == 0
    return {
        "ok": ship,
        "ship_heuristic": ship,
        "score": score,
        "issues": issues,
        "ok_notes": ok,
        "link_count": len(a_tags),
        "href_sample": hrefs[:12],
        "gate_version": GATE_VERSION,
    }


def scan_file(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        return {"ok": False, "error": f"Datei fehlt: {p}"}
    try:
        html = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}
    out = scan_html_text(html)
    out["path"] = str(p)
    return out


def scan_url(url: str, *, timeout: int = 15) -> dict[str, Any]:
    u = (url or "").strip()
    if not u.startswith("http"):
        return {"ok": False, "error": "URL braucht http(s)"}
    try:
        import urllib.request

        req = urllib.request.Request(u, headers={"User-Agent": "WebschmiedeUxGate/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(800_000).decode("utf-8", errors="replace")
            code = int(getattr(r, "status", None) or r.getcode())
        scan = scan_html_text(body, base_url=u)
        scan["http_status"] = code
        scan["url"] = u
        if code >= 400:
            scan["ok"] = False
            scan["issues"] = [f"HTTP {code}"] + list(scan.get("issues") or [])
        return scan
    except Exception as e:
        return {"ok": False, "error": str(e)[:200], "url": u}


def format_scan_report(scan: dict[str, Any]) -> str:
    if scan.get("error"):
        return f"UX-Gate: Fehler – {scan['error']}"
    lines = [
        f"UX- + Fact-Gate (Heuristik {scan.get('gate_version') or GATE_VERSION})",
        f"Score ≈ {scan.get('score', '?')}/100 · Heuristik-OK: {'ja' if scan.get('ship_heuristic') else 'nein'}",
    ]
    if scan.get("url"):
        lines.append(f"URL: {scan['url']} (HTTP {scan.get('http_status', '?')})")
    if scan.get("path"):
        lines.append(f"Datei: {scan['path']}")
    if scan.get("ok_notes"):
        lines.append("Positiv: " + "; ".join(scan["ok_notes"][:6]))
    if scan.get("issues"):
        lines.append("Offen:")
        for i in scan["issues"]:
            lines.append(f"• {i}")
    else:
        lines.append("Keine automatischen HTML-Probleme. Trotzdem kurz Mobile mit Auge prüfen.")
    lines.append(
        "Das ersetzt keinen echten Blick aufs Handy. "
        "Erst wenn Checklist + Auge ok: als fertig bezeichnen."
    )
    return "\n".join(lines)


def status_for_christian() -> str:
    lines = [
        "Vor jeder „fertig“-Meldung gilt das UX- + Fact-Gate:",
        "Fakten, Links/Buttons, Design/Abstände, Mobile, sinnvoller Flow, Funktion.",
        "Telegram: „ux check https://…“ oder „ux check datei app/static/….html“",
        "Cursor-Aufträge haben die Checkliste im Prompt.",
    ]
    return "\n".join(lines)

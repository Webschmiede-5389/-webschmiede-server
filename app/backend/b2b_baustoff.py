"""Baustoffhandel-Pilot: WA-Bestellparse, Preislisten-Vergleich, Reklamations-Vorsortierung.

Kein ERP-Anschluss, kein Meta-Live ohne Token. Deterministisch + Demo-Katalog.
"""
from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Demo-Katalog fuer Parse-Matching (Pilot ohne ERP-API)
DEMO_CATALOG = [
    {"artnr": "KNAUF-RB-25", "ean": "4006379091234", "name": "Knauf Rotband 25 kg", "aliases": ["rotband", "knauf rotband", "gipsputz rotband"], "einheit": "Sack", "lager": 120, "vk": 14.9},
    {"artnr": "KNAUF-GK-12", "ean": "4006379012345", "name": "Knauf Gipskarton 12,5 mm", "aliases": ["gipskarton", "gkplatte", "rigips"], "einheit": "Platte", "lager": 80, "vk": 8.4},
    {"artnr": "PROF-CW100", "ean": "4012345678901", "name": "CW-Profil 100 mm", "aliases": ["cw profil", "cw-profil", "profil cw", "trockenbauprofil"], "einheit": "Stange", "lager": 200, "vk": 3.2},
    {"artnr": "PROF-UW100", "ean": "4012345678902", "name": "UW-Profil 100 mm", "aliases": ["uw profil", "uw-profil", "profil uw"], "einheit": "Stange", "lager": 180, "vk": 2.9},
    {"artnr": "CEM-42-25", "ean": "4001234567890", "name": "Zement CEM II 25 kg", "aliases": ["zement", "cem ii", "portlandzement"], "einheit": "Sack", "lager": 60, "vk": 6.5},
    {"artnr": "ISO-MW-140", "ean": "4009876543210", "name": "Mineralwolle 140 mm", "aliases": ["daemmung", "mineralwolle", "glaswolle", "daemmplatte"], "einheit": "Paket", "lager": 40, "vk": 28.0},
]

_UNIT_RE = re.compile(
    r"(?P<qty>\d+(?:[.,]\d+)?)\s*(?P<unit>sack|saecke|stueck|stk|st|platte|platten|stange|stangen|paket|pakete|rolle|rollen|m2|qm|m²)?\s*(?P<name>[a-zA-ZäöüÄÖÜß0-9\-\./ ]{3,60})",
    re.I,
)
_ORDER_NR_RE = re.compile(r"(?:auftrag|lieferschein|ls|bestellung|abo?)\s*[#:.]?\s*(\d{4,10})", re.I)
_DEST_RE = re.compile(
    r"(?:nach|lieferung(?:sort)?|baustelle)\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ]?[a-zäöüß]+){0,2})",
    re.I,
)


def pilot_pack() -> dict[str, Any]:
    return {
        "ok": True,
        "name": "Baustoffhandel Standort-Pilot (30 Tage)",
        "target": "Niederlassung Baustoff-/Fachhandel (z.B. Eurobaustoff-Verbund)",
        "hosting": "Hetzner Nuernberg, getrennte Hosts web/auto – Daten DE",
        "use_cases": [
            {
                "id": "wa_order",
                "title": "Handwerker-WhatsApp-Bestellung",
                "status": "demo_ready",
                "needs": "Meta WhatsApp Business Token fuer Live-Inbound",
                "api": "POST /api/b2b/baustoff/parse-order",
            },
            {
                "id": "price_compare",
                "title": "Preis-/Lieferantenabgleich",
                "status": "live",
                "needs": "Zwei CSV-Preislisten (Artikelnr/EAN + Preis)",
                "api": "POST /api/b2b/baustoff/compare",
            },
            {
                "id": "complaint",
                "title": "Reklamations-Vorsortierung",
                "status": "live",
                "needs": "Mail-/WA-Text (ERP-Match spaeter)",
                "api": "POST /api/b2b/baustoff/complaint",
            },
        ],
        "pitch_30_days": (
            "30 Tage Pilot an einem Standort: WhatsApp-Bestellungen von bis zu fuenf "
            "Stamm-Handwerkern und/oder taeglicher Preislisten-Abgleich. "
            "Mitarbeiter geben nur noch frei. Wenn spuerbar Zeit gespart wird, "
            "Monatsmodell. Sonst abschalten. Kein tiefer ERP-Eingriff noetig fuer den Start."
        ),
        "honest_limits": [
            "Kein direkter ERP-Schreibzugriff im Pilot (Export/API spaeter)",
            "WhatsApp-Inbound erst nach Meta-Credentials",
            "Kein automatischer Versand an Kunden ohne Freigabe",
            "Kein Helsinki – Hosting Nuernberg",
        ],
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _norm(s: str) -> str:
    s = (s or "").lower().strip()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s)


def _num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    s = str(v).strip().replace("€", "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _norm_key(k: str) -> str:
    k = _norm(k or "")
    return "".join(c if c.isalnum() else "_" for c in k).strip("_")


def parse_csv_rows(content: bytes) -> list[dict[str, Any]]:
    text = content.decode("utf-8-sig", errors="replace")
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
    except Exception:
        dialect = csv.excel
        dialect.delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    rows: list[dict[str, Any]] = []
    for raw in reader:
        if not raw:
            continue
        norm = {_norm_key(k): (v or "").strip() for k, v in raw.items() if k}
        art = (
            norm.get("artnr")
            or norm.get("artikelnummer")
            or norm.get("artikel")
            or norm.get("sku")
            or norm.get("ean")
            or norm.get("gtin")
            or ""
        )
        name = (
            norm.get("name")
            or norm.get("bezeichnung")
            or norm.get("titel")
            or norm.get("produkt")
            or ""
        )
        price = _num(
            norm.get("preis")
            or norm.get("ek")
            or norm.get("einkauf")
            or norm.get("einkaufspreis")
            or norm.get("nettopreis")
            or norm.get("vk")
        )
        lieferant = norm.get("lieferant") or norm.get("hersteller") or norm.get("supplier") or ""
        if not art and not name:
            continue
        rows.append(
            {
                "artnr": art,
                "ean": norm.get("ean") or norm.get("gtin") or "",
                "name": name,
                "preis": price,
                "lieferant": lieferant,
            }
        )
    return rows


def compare_price_lists(
    content_a: bytes,
    content_b: bytes,
    *,
    label_a: str = "Liste A",
    label_b: str = "Liste B",
    outlier_pct: float = 5.0,
) -> dict[str, Any]:
    """Vergleicht zwei Preislisten. Markiert Erhöhungen und guenstigere Quelle."""
    rows_a = parse_csv_rows(content_a)
    rows_b = parse_csv_rows(content_b)

    def key(r: dict[str, Any]) -> str:
        return _norm(r.get("artnr") or r.get("ean") or r.get("name") or "")

    map_a = {key(r): r for r in rows_a if key(r)}
    map_b = {key(r): r for r in rows_b if key(r)}
    keys = sorted(set(map_a) | set(map_b))
    diffs: list[dict[str, Any]] = []
    cheaper_b = 0
    cheaper_a = 0
    outliers = 0
    for k in keys:
        a = map_a.get(k)
        b = map_b.get(k)
        pa = a.get("preis") if a else None
        pb = b.get("preis") if b else None
        delta = None
        delta_pct = None
        if pa is not None and pb is not None and pa != 0:
            delta = round(pb - pa, 4)
            delta_pct = round((delta / pa) * 100, 2)
        flag = []
        if delta_pct is not None and abs(delta_pct) >= outlier_pct:
            outliers += 1
            flag.append("ausreisser")
            if delta_pct > 0:
                flag.append("teurer_in_b")
            else:
                flag.append("guenstiger_in_b")
        if pa is not None and pb is not None:
            if pb < pa:
                cheaper_b += 1
            elif pa < pb:
                cheaper_a += 1
        if a is None:
            flag.append("nur_in_b")
        if b is None:
            flag.append("nur_in_a")
        diffs.append(
            {
                "key": k,
                "artnr": (a or b or {}).get("artnr") or "",
                "name": (a or b or {}).get("name") or "",
                "preis_a": pa,
                "preis_b": pb,
                "delta": delta,
                "delta_pct": delta_pct,
                "flags": flag,
                "lieferant_a": (a or {}).get("lieferant") or label_a,
                "lieferant_b": (b or {}).get("lieferant") or label_b,
            }
        )

    ranked = sorted(
        [d for d in diffs if d.get("delta_pct") is not None],
        key=lambda d: abs(d["delta_pct"] or 0),
        reverse=True,
    )
    morning = []
    for d in ranked[:8]:
        if "ausreisser" not in (d.get("flags") or []):
            continue
        direction = "verteuert" if (d.get("delta_pct") or 0) > 0 else "guenstiger"
        morning.append(
            f"{d.get('name') or d.get('artnr')}: {label_b} ist {abs(d['delta_pct']):.1f}% {direction} "
            f"gegenueber {label_a}."
        )
    if not morning:
        morning.append("Keine Ausreisser ueber der Schwelle. Listen weitgehend stabil.")

    return {
        "ok": True,
        "engine": "baustoff-compare-local",
        "label_a": label_a,
        "label_b": label_b,
        "outlier_pct": outlier_pct,
        "stats": {
            "zeilen_a": len(rows_a),
            "zeilen_b": len(rows_b),
            "gemeinsam": len(set(map_a) & set(map_b)),
            "ausreisser": outliers,
            "guenstiger_in_b": cheaper_b,
            "guenstiger_in_a": cheaper_a,
        },
        "morning_briefing": morning,
        "top_diffs": ranked[:40],
        "rows": diffs[:500],
        "note": "Kein ERP-Import. CSV-Vergleich fuer Einkaufs-Pilot.",
    }


def parse_whatsapp_order(
    text: str,
    *,
    catalog: list[dict[str, Any]] | None = None,
    from_phone: str = "",
) -> dict[str, Any]:
    """Extrahiert Mengen/Produkte aus Handwerker-WhatsApp-Text (heuristisch)."""
    raw = (text or "").strip()
    if not raw:
        return {"ok": False, "error": "text fehlt"}
    catalog = catalog or DEMO_CATALOG
    dest_m = _DEST_RE.search(raw)
    destination = (dest_m.group(1).strip() if dest_m else "")[:80]
    when = ""
    low = raw.lower()
    for hint in ("heute nachmittag", "heute", "morgen frueh", "morgen", "sofort", "dringend"):
        if hint in low or hint.replace("ue", "ü") in low:
            when = hint
            break

    items: list[dict[str, Any]] = []
    # Zuerst an "und/sowie" splitten, sonst frisst die Regex die naechste Menge mit
    chunks = re.split(r"\s+(?:und|sowie|plus|/|,)\s+", raw, flags=re.I)
    for chunk in chunks:
        for m in _UNIT_RE.finditer(chunk):
            qty = _num(m.group("qty")) or 1.0
            unit = (m.group("unit") or "").strip() or "Stk"
            name_frag = (m.group("name") or "").strip(" .,;")
            name_frag = re.split(r"\s+(?:nach|fuer|für|lieferung)\s+", name_frag, maxsplit=1, flags=re.I)[
                0
            ].strip()
            if len(name_frag) < 3:
                continue
            match = _match_catalog(name_frag, catalog)
            items.append(
                {
                    "qty": qty,
                    "unit": unit,
                    "raw_name": name_frag,
                    "matched": bool(match),
                    "artnr": (match or {}).get("artnr") or "",
                    "ean": (match or {}).get("ean") or "",
                    "name": (match or {}).get("name") or name_frag,
                    "lager": (match or {}).get("lager"),
                    "vk": (match or {}).get("vk"),
                    "stock_ok": None
                    if not match
                    else (match.get("lager") is None or float(match.get("lager") or 0) >= qty),
                }
            )

    # Fallback: Katalog-Alias ohne Menge
    if not items:
        for prod in catalog:
            for alias in prod.get("aliases") or []:
                if _norm(alias) in _norm(raw):
                    items.append(
                        {
                            "qty": 1,
                            "unit": prod.get("einheit") or "Stk",
                            "raw_name": alias,
                            "matched": True,
                            "artnr": prod.get("artnr") or "",
                            "ean": prod.get("ean") or "",
                            "name": prod.get("name") or alias,
                            "lager": prod.get("lager"),
                            "vk": prod.get("vk"),
                            "stock_ok": True,
                        }
                    )
                    break

    total = 0.0
    for it in items:
        if it.get("vk") is not None and it.get("qty") is not None:
            total += float(it["vk"]) * float(it["qty"])

    confidence = 0.2
    if items:
        matched = sum(1 for i in items if i.get("matched"))
        confidence = round(0.35 + 0.55 * (matched / max(len(items), 1)), 2)
        if destination:
            confidence = min(0.95, confidence + 0.05)

    draft = {
        "status": "draft",
        "needs_approval": True,
        "from_phone": from_phone[:40],
        "destination": destination,
        "when_hint": when,
        "items": items,
        "schaetzung_vk": round(total, 2) if total else None,
        "confidence": confidence,
        "reply_draft": _reply_draft(items, destination, when),
        "pickup_qr_hint": "Nach Freigabe: Abhol-Code/QR aus ERP oder Portal erzeugen (Pilot: Platzhalter).",
        "note": "Kein ERP-Schreiben. Vertrieb gibt im Dashboard frei.",
    }
    return {"ok": True, "engine": "baustoff-wa-parse-local", "order": draft, "source_text": raw[:2000]}


def _match_catalog(frag: str, catalog: list[dict[str, Any]]) -> dict[str, Any] | None:
    n = _norm(frag)
    if not n:
        return None
    best = None
    best_score = 0
    for prod in catalog:
        names = [prod.get("name") or ""] + list(prod.get("aliases") or [])
        for cand in names:
            c = _norm(cand)
            if not c:
                continue
            score = 0
            if c in n or n in c:
                score = min(len(c), len(n))
            else:
                tokens = [t for t in c.split() if len(t) > 2]
                hit = sum(1 for t in tokens if t in n)
                if hit:
                    score = hit * 3
            if score > best_score:
                best_score = score
                best = prod
    return best if best_score >= 3 else None


def _reply_draft(items: list[dict[str, Any]], destination: str, when: str) -> str:
    if not items:
        return (
            "Danke fuer Ihre Nachricht. Ich konnte die Artikel noch nicht eindeutig lesen. "
            "Bitte Menge und Produkt kurz nennen, dann pruefen wir Lager und melden uns."
        )
    lines = ["Danke, ich habe das als Bestellentwurf erfasst:"]
    for it in items:
        stock = ""
        if it.get("matched") and it.get("stock_ok") is False:
            stock = " (Lager pruefen)"
        lines.append(f"- {it['qty']:g} {it.get('unit') or 'Stk'} {it.get('name')}{stock}")
    if destination:
        lines.append(f"Lieferort/Abholung: {destination}")
    if when:
        lines.append(f"Zeitwunsch: {when}")
    lines.append("Unser Vertrieb gibt das gleich frei. Sie bekommen dann die Bestaetigung.")
    return "\n".join(lines)


def classify_complaint(text: str, *, subject: str = "") -> dict[str, Any]:
    blob = _norm(f"{subject}\n{text}")
    raw = (text or "").strip()
    if not raw and not subject:
        return {"ok": False, "error": "text fehlt"}

    categories = []
    scores = {
        "transportschaden": 0,
        "falschlieferung": 0,
        "fehlmenge": 0,
        "qualitaet": 0,
        "rechnung": 0,
        "verzoegerung": 0,
    }
    rules = {
        "transportschaden": ["transportschaden", "gebrochen", "zerbrochen", "beschaedigt", "kaputt", "nass geworden", "folie gerissen"],
        "falschlieferung": ["falsch geliefert", "falsche ware", "vertauscht", "nicht bestellt", "falsche artikel"],
        "fehlmenge": ["fehlt", "fehlmenge", "zu wenig", "nicht vollstaendig", "unterlieferung"],
        "qualitaet": ["qualitaet", "mangel", "defekt", "ausschuss", "reklamation"],
        "rechnung": ["rechnung", "gutschrift", "preis falsch", "doppel berechnet"],
        "verzoegerung": ["zu spaet", "verzoeger", "nicht angekommen", "warte seit"],
    }
    for cat, kws in rules.items():
        for kw in kws:
            if kw in blob:
                scores[cat] += 2
    categories = [c for c, s in sorted(scores.items(), key=lambda x: -x[1]) if s > 0]
    primary = categories[0] if categories else "ungeklaert"

    order_nrs = list(dict.fromkeys(_ORDER_NR_RE.findall(raw + " " + subject)))
    prio = "normal"
    if primary in ("transportschaden", "falschlieferung") or "dringend" in blob:
        prio = "hoch"
    if "sofort" in blob or "baustelle steht" in blob:
        prio = "kritisch"

    suggestion = {
        "transportschaden": "Fotos sichern, Spedition klaeren, Ersatzlieferung oder Gutschrift vorschlagen.",
        "falschlieferung": "Lieferschein vs. Auftrag pruefen, Abholung Falschware + Nachlieferung.",
        "fehlmenge": "Kommission/Lagerbuchung pruefen, Restlieferung anbieten.",
        "qualitaet": "Charge/Foto an QM, Ruecknahme oder Austausch.",
        "rechnung": "Beleg an Buchhaltung, Gutschrift-Entwurf vorbereiten.",
        "verzoegerung": "Tour/Status pruefen, Kunden mit ETA informieren.",
        "ungeklaert": "Manuell zuordnen, Rueckfrage an Absender.",
    }.get(primary, "Manuell pruefen.")

    ticket = {
        "status": "vorsortiert",
        "priority": prio,
        "primary": primary,
        "categories": categories,
        "order_candidates": order_nrs,
        "suggestion": suggestion,
        "staff_summary": (
            f"{primary.upper()} · Prio {prio}"
            + (f" · Auftrag/LS {', '.join(order_nrs)}" if order_nrs else " · keine Auftragsnr erkannt")
            + f". {suggestion}"
        ),
        "needs_human": True,
        "erp_note": "ERP-Suche nach Lieferschein erst nach API/Export-Anbindung.",
    }
    return {
        "ok": True,
        "engine": "baustoff-complaint-local",
        "ticket": ticket,
        "source_subject": subject[:200],
        "source_text": raw[:4000],
    }


def ensure_order_tables(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS b2b_orders (
            id          TEXT PRIMARY KEY,
            created_at  TEXT DEFAULT (datetime('now')),
            updated_at  TEXT DEFAULT (datetime('now')),
            kunde_id    TEXT,
            from_phone  TEXT,
            status      TEXT DEFAULT 'draft',
            source_text TEXT,
            order_json  TEXT,
            error       TEXT
        )
        """
    )
    db.commit()


def save_order_draft(
    db: sqlite3.Connection,
    *,
    kunde_id: str,
    parsed: dict[str, Any],
) -> dict[str, Any]:
    ensure_order_tables(db)
    if not parsed.get("ok"):
        return parsed
    oid = uuid.uuid4().hex[:12]
    order = parsed.get("order") or {}
    kid = (kunde_id or "DEMO").upper()[:32]
    db.execute(
        """
        INSERT INTO b2b_orders (id, kunde_id, from_phone, status, source_text, order_json)
        VALUES (?,?,?,?,?,?)
        """,
        (
            oid,
            kid,
            (order.get("from_phone") or "")[:40],
            "draft",
            (parsed.get("source_text") or "")[:4000],
            json.dumps(order, ensure_ascii=False),
        ),
    )
    db.commit()
    return {"ok": True, "id": oid, "kunde_id": kid, "status": "draft", "order": order}


def list_orders(db: sqlite3.Connection, kunde_id: str, limit: int = 40) -> list[dict[str, Any]]:
    ensure_order_tables(db)
    kid = (kunde_id or "DEMO").upper()
    cur = db.execute(
        "SELECT * FROM b2b_orders WHERE kunde_id=? ORDER BY created_at DESC LIMIT ?",
        (kid, limit),
    )
    out = []
    for r in cur.fetchall():
        d = dict(r)
        try:
            d["order"] = json.loads(d.pop("order_json") or "{}")
        except Exception:
            d["order"] = {}
        out.append(d)
    return out


def approve_order(db: sqlite3.Connection, order_id: str) -> dict[str, Any]:
    ensure_order_tables(db)
    cur = db.execute("SELECT * FROM b2b_orders WHERE id=?", (order_id,))
    row = cur.fetchone()
    if not row:
        return {"ok": False, "error": "Order nicht gefunden"}
    d = dict(row)
    try:
        order = json.loads(d.get("order_json") or "{}")
    except Exception:
        order = {}
    order["status"] = "approved"
    order["approved_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    order["pickup_code"] = f"ABH-{order_id.upper()}"
    db.execute(
        """
        UPDATE b2b_orders
        SET status='approved', order_json=?, updated_at=datetime('now'), error=NULL
        WHERE id=?
        """,
        (json.dumps(order, ensure_ascii=False), order_id),
    )
    db.commit()
    reply = order.get("reply_draft") or ""
    if order.get("pickup_code"):
        reply = (reply + f"\n\nAbholcode: {order['pickup_code']}").strip()
    return {
        "ok": True,
        "id": order_id,
        "status": "approved",
        "order": order,
        "customer_reply": reply,
        "note": "Antwort erst nach Meta/WhatsApp-Freigabe senden. Kein Auto-Send.",
    }


def demo_catalog_csv() -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["artnr", "ean", "name", "preis", "lieferant"])
    for p in DEMO_CATALOG:
        w.writerow([p["artnr"], p["ean"], p["name"], p.get("vk") or "", "DemoLager"])
    return buf.getvalue()

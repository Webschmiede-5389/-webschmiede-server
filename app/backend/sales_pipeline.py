"""Sales-Pipeline: Invite → Discovery → Research/Angebot → Preis → Pay → Weiter.

Christian: „hier die Mail“ → Kunde bekommt Discovery-Link.
Nach Ausfüllen: Research + Pain-Angebot (ohne Preis) per Mail.
Christian setzt Preis → Checkout/Vertrag.
Nach Stripe: bestehendes provision.py.

Kein Auto-Spam ohne Invite. Website-Lead startet dieselbe Kette.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
SITE = "https://digitalehandwerkskunst.de"
STATE_DIR = Path(
    os.getenv(
        "SALES_PIPELINE_DIR",
        str(Path(__file__).resolve().parent.parent / "vault" / "sales"),
    )
)

# Map Discovery-Tier → Stripe package id (agency_packages)
TIER_TO_PACKAGE = {
    "beleg": "buchhaltung_beleg",
    "sync": "buchhaltung_sync",
    "silo": "buchhaltung_silo",
    "starter": "starter",
    "pro": "pro",
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_tables(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_deals (
            id TEXT PRIMARY KEY,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            email TEXT NOT NULL,
            firma TEXT,
            kontakt TEXT,
            phone TEXT,
            product TEXT DEFAULT 'buchhaltung',
            status TEXT DEFAULT 'invited',
            discovery_id TEXT,
            discovery_token TEXT,
            research_json TEXT,
            offer_json TEXT,
            price_setup_eur INTEGER,
            price_monthly_eur INTEGER,
            kunde_id TEXT,
            checkout_url TEXT,
            meta_json TEXT
        )
        """
    )
    db.commit()
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def _row(r: sqlite3.Row | None) -> dict[str, Any] | None:
    if not r:
        return None
    d = dict(r)
    for key in ("research_json", "offer_json", "meta_json"):
        raw = d.pop(key, None)
        name = key.replace("_json", "")
        if raw:
            try:
                d[name] = json.loads(raw)
            except Exception:
                d[name] = None
        else:
            d[name] = None
    return d


def public_deal(d: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "id": d.get("id"),
        "email": d.get("email"),
        "firma": d.get("firma"),
        "kontakt": d.get("kontakt"),
        "phone": d.get("phone"),
        "product": d.get("product"),
        "status": d.get("status"),
        "discovery_id": d.get("discovery_id"),
        "discovery_link": (
            f"{SITE}/buchhaltung-onboarding.html?id={d.get('discovery_id')}&t={d.get('discovery_token')}"
            if d.get("discovery_id") and d.get("discovery_token")
            else None
        ),
        "research": d.get("research"),
        "offer": d.get("offer"),
        "price_setup_eur": d.get("price_setup_eur"),
        "price_monthly_eur": d.get("price_monthly_eur"),
        "kunde_id": d.get("kunde_id"),
        "checkout_url": d.get("checkout_url"),
        "created_at": d.get("created_at"),
        "updated_at": d.get("updated_at"),
    }


def get_deal(db: sqlite3.Connection, deal_id: str) -> dict[str, Any] | None:
    ensure_tables(db)
    r = db.execute("SELECT * FROM sales_deals WHERE id = ?", (deal_id,)).fetchone()
    return _row(r)


def list_deals(db: sqlite3.Connection, limit: int = 40) -> dict[str, Any]:
    ensure_tables(db)
    rows = db.execute(
        """
        SELECT id, created_at, updated_at, email, firma, status, product,
               price_setup_eur, price_monthly_eur, kunde_id, discovery_id
        FROM sales_deals ORDER BY datetime(updated_at) DESC LIMIT ?
        """,
        (max(1, min(limit, 200)),),
    ).fetchall()
    return {"ok": True, "count": len(rows), "deals": [dict(r) for r in rows]}


def _send(to: str, subject: str, body_html: str, text: str) -> dict[str, Any]:
    from agency_mail import send_html_email
    from email_templates import email_shell

    html = email_shell(
        hero_title=subject.split("·")[0].strip()[:80],
        hero_subtitle="Webschmiede · Digitale Handwerkskunst",
        preheader=subject[:120],
        body_html=body_html,
    )
    send_html_email(to=to, subject=subject, html=html, text=text)
    return {"ok": True, "to": to}


def invite(
    db: sqlite3.Connection,
    *,
    email: str,
    firma: str = "",
    kontakt: str = "",
    phone: str = "",
    product: str = "buchhaltung",
    send_email: bool = True,
    website: str = "",
) -> dict[str, Any]:
    """Christian gibt Mail → Discovery-Session + Einladungsmail."""
    import buchhaltung_onboarding as bh

    ensure_tables(db)
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        return {"ok": False, "error": "Gültige E-Mail nötig"}

    session = bh.create_session(db, firma=firma, kontakt=kontakt or firma, email=email)
    deal_id = uuid.uuid4().hex[:12]
    meta = {"website": (website or "").strip(), "invited_at": _now()}
    db.execute(
        """
        INSERT INTO sales_deals (
          id, email, firma, kontakt, phone, product, status,
          discovery_id, discovery_token, meta_json
        ) VALUES (?, ?, ?, ?, ?, ?, 'invited', ?, ?, ?)
        """,
        (
            deal_id,
            email,
            (firma or "").strip()[:120],
            (kontakt or "").strip()[:120],
            (phone or "").strip()[:40],
            (product or "buchhaltung").strip()[:40],
            session["id"],
            session["access_token"],
            json.dumps(meta, ensure_ascii=False),
        ),
    )
    db.commit()
    deal = get_deal(db, deal_id)
    assert deal
    link = public_deal(deal)["discovery_link"]
    mail_result = None
    if send_email:
        mail_result = _mail_invite(deal, link or "")
    # Optional WhatsApp text if messaging ready
    wa = _try_whatsapp_ping(phone, link or "", firma)
    out = public_deal(deal)
    out["mail"] = mail_result
    out["whatsapp"] = wa
    out["owner_ping"] = _notify_christian(
        get_deal(db, deal_id) or deal,
        stage="invited",
        db=db,
        extra=f"Kunden-Mail: {'ok' if (mail_result or {}).get('ok') else 'prüfen'}",
    )
    out["next"] = "Kunde füllt Discovery aus. Danach Research + Pain-Angebot automatisch."
    return out


def _mail_invite(deal: dict[str, Any], link: str) -> dict[str, Any]:
    from email_templates import email_button

    name = deal.get("kontakt") or deal.get("firma") or "dort"
    firma = deal.get("firma") or "Ihr Betrieb"
    body = f"""
    <p>Hallo {name},</p>
    <p>schön, dass wir ins Gespräch gekommen sind. Damit wir für <strong>{firma}</strong>
    nichts Rätselraten, brauchen wir ein paar ehrliche Angaben: welche Tools ihr nutzt,
    wo die Zeit wegfließt, was in 30 Tagen besser sein soll.</p>
    <p>Das dauert wenige Minuten. Am Ende seht ihr unsere Einschätzung.</p>
    <p style="margin:24px 0;">{email_button(link, "Onboarding starten")}</p>
    <p style="color:#666;font-size:13px;">Link: {link}</p>
    <p>Viele Grüße<br>Christian · Webschmiede</p>
    """
    text = (
        f"Hallo {name},\n\n"
        f"bitte Onboarding für {firma} starten:\n{link}\n\n"
        f"Christian · Webschmiede\n"
    )
    return _send(
        deal["email"],
        f"Onboarding starten · {firma} · Webschmiede",
        body,
        text,
    )


def _try_whatsapp_ping(phone: str, link: str, firma: str) -> dict[str, Any]:
    phone = (phone or "").strip()
    if not phone:
        return {"ok": False, "skipped": True, "detail": "Keine Telefonnummer"}
    try:
        import messaging as msg

        text = (
            f"Hallo, hier Christian von der Webschmiede. "
            f"Für {firma or 'euch'} liegt das Onboarding bereit:\n{link}"
        )
        if hasattr(msg, "send_whatsapp"):
            return msg.send_whatsapp(phone, text)
        if hasattr(msg, "send_message"):
            return msg.send_message(channel="whatsapp", to=phone, text=text)
        return {"ok": False, "skipped": True, "detail": "messaging.send_whatsapp fehlt"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160], "hint": "WhatsApp-Token in Agency-Setup setzen"}


def research_company(
    *,
    firma: str,
    website: str = "",
    tools: list[str] | None = None,
    answers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Leichte Firmen-Recherche: Website-Signale + Pain-Mapping. Kein Trustpilot-Claim."""
    tools = tools or []
    answers = answers or {}
    signals: dict[str, Any] = {}
    url = (website or "").strip()
    if not url and answers.get("website"):
        url = str(answers.get("website"))
    # Heuristik Domain aus Firma
    if not url and firma:
        guess = re.sub(r"[^a-z0-9]", "", firma.lower())
        if len(guess) > 3:
            url = f"https://www.{guess}.de"

    if url:
        try:
            import sys
            from pathlib import Path as P

            root = P(__file__).resolve().parents[2]
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            from akquise.enrichment import crawl_website, normalize_url

            nu = normalize_url(url)
            lead = {"website": nu, "name": firma, "url": nu}
            crawled = crawl_website(lead, cfg={}) or {}
            signals = crawled if isinstance(crawled, dict) else {}
            if "signals" in signals and isinstance(signals["signals"], dict):
                signals = signals["signals"]
        except Exception as e:
            signals = {"error": str(e)[:160], "checked": False}

    pains: list[dict[str, str]] = []
    # Tool-basierte Pains
    tset = {x.lower() for x in tools}
    if "whatsapp_belege" in tset or "imap" in tset:
        pains.append(
            {
                "id": "beleg_chaos",
                "label": "Belege verstreut in Mail/WhatsApp",
                "solution": "Eine Beleg-Pipeline: Postfach → Monatsmappe → Steuerberater",
            }
        )
    if "excel" in tset and not (tset & {"lexware", "sevdesk"}):
        pains.append(
            {
                "id": "excel_only",
                "label": "Zahlen leben in Excel, nicht im System",
                "solution": "Monats-CSV + Sync statt Sonntag-Tipparbeit",
            }
        )
    if tset & {"crm", "projektboard"} and tset & {"lexware", "sevdesk"}:
        pains.append(
            {
                "id": "silos",
                "label": "CRM/Board und Buchhaltung laufen nebeneinander",
                "solution": "System-Brücke: erledigte Jobs landen automatisch im Export",
            }
        )
    elif tset & {"lexware", "sevdesk"} and "portal" in tset:
        pains.append(
            {
                "id": "sync_gap",
                "label": "Portal und Buchhaltung sind nicht verbunden",
                "solution": "Finanz-Sync: abgeschlossene Jobs landen im Monatsexport",
            }
        )
    if "meta_ads" in tset:
        pains.append(
            {
                "id": "meta_bills",
                "label": "Meta-Rechnungen versanden im Postfach",
                "solution": "Automatische Sortierung der Ads-Belege ins Monatspaket",
            }
        )
    if not pains:
        pains.append(
            {
                "id": "time_drain",
                "label": answers.get("zeitfresser") or "Zeitfresser ohne Kundenbezahlung",
                "solution": "Ein Prozess in 30 Tagen spürbar entlasten, Rest später",
            }
        )

    # Website-Signale als Beobachtungen
    observations: list[str] = []
    if signals.get("has_website") is False or signals.get("error"):
        observations.append("Website schwer erreichbar oder unsicher, Auftritt prüfen")
    if signals.get("title"):
        observations.append(f"Website-Titel: {signals.get('title')[:80]}")
    if signals.get("only_social_site"):
        observations.append("Auftritt wirkt stark social-lastig, wenig eigene Conversion")
    if signals.get("delivery_platforms"):
        observations.append(
            "Fremdplattformen erkannt: " + ", ".join(signals.get("delivery_platforms") or [])[:120]
        )
    observations.append(
        "Foren/Trustpilot: kein Auto-Scraping (rechtlich/technisch). "
        "Christian kann Bewertungen im Gespräch ergänzen."
    )

    return {
        "as_of": _now(),
        "firma": firma,
        "website": url or None,
        "signals": {
            "checked": bool(signals.get("checked")),
            "title": signals.get("title"),
            "https": signals.get("https"),
            "error": signals.get("error"),
        },
        "pains": pains[:6],
        "observations": observations,
        "answers_excerpt": {
            "ziel_30": answers.get("ziel_30"),
            "zeitfresser": answers.get("zeitfresser"),
            "wer_tippt": answers.get("wer_tippt"),
            "wuensche": (answers.get("wuensche") or "")[:800],
        },
        "wuensche": (answers.get("wuensche") or "").strip()[:2000],
        "uncertain": bool(signals.get("error") or not signals.get("checked")),
        "honest": "Research = Website-Signale + eure Angaben. Kein Fake-Trustpilot-Report.",
    }


def build_pain_offer(
    *,
    research: dict[str, Any],
    recommended: dict[str, Any] | None,
    with_prices: bool = False,
) -> dict[str, Any]:
    tier = (recommended or {}).get("tier") or "beleg"
    pkg = recommended or {}
    pains = research.get("pains") or []
    wuensche = (research.get("wuensche") or "").strip()
    offer = {
        "type": "pain_assessment" if not with_prices else "priced_offer",
        "tier": tier,
        "name": pkg.get("name") or "Beleg-Pipeline",
        "tagline": pkg.get("tagline") or "",
        "pains": pains,
        "observations": research.get("observations") or [],
        "wuensche": wuensche[:2000],
        "value_promise": (
            "Ihr Steuerberater bekommt sortierte Unterlagen statt Chaos. "
            "Ihr spart die Sonntags-Suche nach Belegen. "
            "Wir betreiben die Automation auf unseren Servern in Deutschland."
        ),
        "not_included": "Keine laufende Buchführung, keine Steuererklärung.",
        "with_prices": with_prices,
        "as_of": _now(),
    }
    if with_prices:
        offer["setup_eur"] = pkg.get("setup_eur")
        offer["monthly_eur"] = pkg.get("monthly_eur")
    else:
        offer["price_note"] = (
            "Preise bewusst noch nicht im ersten Schreiben. "
            "Nach eurem Go schicken wir das konkrete Angebot mit Zahlen."
        )
    return offer


def on_discovery_complete(db: sqlite3.Connection, discovery_id: str) -> dict[str, Any]:
    """Hook nach Wizard: Research bauen, Christian um Freigabe bitten (kein Auto-Send)."""
    import buchhaltung_onboarding as bh

    ensure_tables(db)
    r = db.execute(
        "SELECT * FROM sales_deals WHERE discovery_id = ? ORDER BY datetime(created_at) DESC LIMIT 1",
        (discovery_id,),
    ).fetchone()
    deal = _row(r)
    if not deal:
        sess = bh.get_raw(db, discovery_id)
        if not sess:
            return {"ok": False, "error": "Kein Deal/Session"}
        deal_id = uuid.uuid4().hex[:12]
        db.execute(
            """
            INSERT INTO sales_deals (
              id, email, firma, kontakt, product, status,
              discovery_id, discovery_token
            ) VALUES (?, ?, ?, ?, 'buchhaltung', 'discovery_done', ?, ?)
            """,
            (
                deal_id,
                (sess.get("email") or "unbekannt@invalid.local"),
                sess.get("firma") or "",
                sess.get("kontakt") or "",
                discovery_id,
                sess.get("access_token") or "",
            ),
        )
        db.commit()
        deal = get_deal(db, deal_id)
    assert deal

    sess = bh.get_raw(db, discovery_id) or {}
    meta = dict(deal.get("meta") or {}) if isinstance(deal.get("meta"), dict) else {}
    research = research_company(
        firma=sess.get("firma") or deal.get("firma") or "",
        website=(meta.get("website") or ""),
        tools=sess.get("tools") or [],
        answers=sess.get("answers") or {},
    )
    offer = build_pain_offer(
        research=research,
        recommended=sess.get("offer"),
        with_prices=False,
    )
    uncertain = bool(research.get("uncertain"))
    wuensche = (research.get("wuensche") or "").strip()
    meta["awaiting_freigabe"] = "pain"
    meta["freigabe_reason"] = (
        "Research unsicher (Website-Check schwach)" if uncertain else "Standard: Kunden-Mail nur nach deiner Freigabe"
    )
    db.execute(
        """
        UPDATE sales_deals
        SET research_json=?, offer_json=?, status='awaiting_freigabe_pain',
            firma=COALESCE(NULLIF(firma,''), ?), meta_json=?,
            updated_at=datetime('now')
        WHERE id=?
        """,
        (
            json.dumps(research, ensure_ascii=False),
            json.dumps(offer, ensure_ascii=False),
            (sess.get("firma") or "")[:120],
            json.dumps(meta, ensure_ascii=False),
            deal["id"],
        ),
    )
    db.commit()
    deal = get_deal(db, deal["id"])
    assert deal
    extra_bits = [
        f"Empfehlung: {(deal.get('offer') or {}).get('name') or '?'}",
        f"Grund Freigabe: {meta.get('freigabe_reason')}",
        f"Dashboard: {SITE}/sales-dashboard.html",
        f"Freigeben: POST /api/sales/deals/{deal['id']}/freigabe  body {{\"action\":\"send_pain\"}}",
    ]
    if wuensche:
        extra_bits.append(f"Kundenwünsche: {wuensche[:400]}")
    owner = _notify_christian(
        deal,
        stage="awaiting_freigabe_pain",
        db=db,
        extra=" · ".join(extra_bits),
    )
    out = public_deal(deal)
    out["mail"] = {"ok": True, "skipped": True, "detail": "Wartet auf deine Freigabe"}
    out["owner_mail"] = owner
    out["needs_freigabe"] = True
    out["wuensche"] = wuensche[:500] if wuensche else ""
    return out


def freigabe(
    db: sqlite3.Connection,
    deal_id: str,
    *,
    action: str = "send_pain",
    note: str = "",
) -> dict[str, Any]:
    """Christian gibt frei → Kunden-Mail / nächster Schritt."""
    deal = get_deal(db, deal_id)
    if not deal:
        return {"ok": False, "error": "Deal unbekannt"}
    action = (action or "send_pain").strip().lower()
    meta = dict(deal.get("meta") or {}) if isinstance(deal.get("meta"), dict) else {}

    if action in ("send_pain", "pain", "einschätzung", "einschaetzung"):
        if deal.get("status") not in ("awaiting_freigabe_pain", "offer_draft", "held"):
            return {
                "ok": False,
                "error": f"Status {deal.get('status')} – Freigabe nur bei awaiting_freigabe_pain",
            }
        mail = _mail_pain_offer(deal)
        meta["awaiting_freigabe"] = None
        meta["freigabe_pain_at"] = _now()
        meta["freigabe_note"] = (note or "")[:300]
        db.execute(
            """
            UPDATE sales_deals
            SET status='offer_draft', meta_json=?, updated_at=datetime('now')
            WHERE id=?
            """,
            (json.dumps(meta, ensure_ascii=False), deal_id),
        )
        db.commit()
        deal = get_deal(db, deal_id)
        assert deal
        ping = _notify_christian(
            deal,
            stage="pain_offer_sent",
            db=db,
            extra="Einschätzung freigegeben und an Kunden gesendet. Als Nächstes Preis setzen.",
        )
        out = public_deal(deal)
        out["mail"] = mail
        out["owner_ping"] = ping
        return out

    if action in ("reject", "hold", "warten"):
        meta["awaiting_freigabe"] = "held"
        meta["freigabe_hold_note"] = (note or "Zurückgehalten")[:300]
        db.execute(
            "UPDATE sales_deals SET status='held', meta_json=?, updated_at=datetime('now') WHERE id=?",
            (json.dumps(meta, ensure_ascii=False), deal_id),
        )
        db.commit()
        return {"ok": True, "status": "held", "note": note}

    return {"ok": False, "error": "action unbekannt (send_pain | hold)"}


def _mail_pain_offer(deal: dict[str, Any]) -> dict[str, Any]:
    from email_templates import email_button

    offer = deal.get("offer") or {}
    firma = deal.get("firma") or "Ihr Betrieb"
    name = deal.get("kontakt") or "dort"
    pains = "".join(
        f"<li><strong>{p.get('label')}</strong><br><span style='color:#666'>{p.get('solution')}</span></li>"
        for p in (offer.get("pains") or [])
    )
    obs = "".join(f"<li>{o}</li>" for o in (offer.get("observations") or [])[:5])
    wu = (offer.get("wuensche") or "").strip()
    wu_html = (
        f"<p><strong>Eure besonderen Hinweise:</strong><br>{wu.replace('<','&lt;')}</p>"
        if wu
        else ""
    )
    dash = f"{SITE}/sales-angebot.html?d={deal['id']}"
    body = f"""
    <p>Hallo {name},</p>
    <p>wir haben eure Angaben zu <strong>{firma}</strong> ausgewertet.
    Hier die Einschätzung ohne Preisdruck, nur Klarheit:</p>
    <p><strong>Empfohlener Rahmen:</strong> {offer.get('name')} – {offer.get('tagline')}</p>
    {wu_html}
    <p><strong>Was wir sehen:</strong></p>
    <ul>{pains or '<li>Zeitfresser in der Belegkette</li>'}</ul>
    <p><strong>Beobachtungen:</strong></p>
    <ul>{obs}</ul>
    <p>{offer.get('value_promise')}</p>
    <p style="color:#666;font-size:13px;">{offer.get('price_note') or ''}</p>
    <p style="margin:24px 0;">{email_button(dash, "Einschätzung ansehen")}</p>
    <p>Wenn das passt, schreibt kurz „passt“ oder antwortet auf diese Mail.
    Dann schicken wir das konkrete Angebot mit Zahlen und den Zahlungslink.</p>
    <p>Christian · Webschmiede</p>
    """
    text = f"Einschätzung für {firma}: {offer.get('name')}\n{dash}\n\nChristian · Webschmiede\n"
    return _send(deal["email"], f"Einschätzung für {firma} · Webschmiede", body, text)


def _notify_christian(
    deal: dict[str, Any],
    *,
    stage: str,
    db: sqlite3.Connection | None = None,
    extra: str = "",
) -> dict[str, Any]:
    try:
        import sales_companion as companion

        return companion.ping_owner(deal, stage=stage, db=db, extra=extra)
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def set_price(
    db: sqlite3.Connection,
    deal_id: str,
    *,
    setup_eur: int | None = None,
    monthly_eur: int | None = None,
    send_offer: bool = True,
) -> dict[str, Any]:
    deal = get_deal(db, deal_id)
    if not deal:
        return {"ok": False, "error": "Deal unbekannt"}
    offer = dict(deal.get("offer") or {})
    # Defaults from discovery tier
    import buchhaltung_onboarding as bh

    tier = offer.get("tier") or "beleg"
    base = bh.PACKAGES.get(tier) or bh.PACKAGES["beleg"]
    setup = int(setup_eur if setup_eur is not None else base["setup_eur"])
    monthly = int(monthly_eur if monthly_eur is not None else base["monthly_eur"])
    research = deal.get("research") or {}
    priced = build_pain_offer(
        research=research,
        recommended={**base, "tier": tier, "name": offer.get("name") or base["name"], "tagline": offer.get("tagline") or base["tagline"]},
        with_prices=True,
    )
    priced["setup_eur"] = setup
    priced["monthly_eur"] = monthly
    priced["pains"] = offer.get("pains") or priced.get("pains")
    db.execute(
        """
        UPDATE sales_deals
        SET price_setup_eur=?, price_monthly_eur=?, offer_json=?,
            status='priced', updated_at=datetime('now')
        WHERE id=?
        """,
        (setup, monthly, json.dumps(priced, ensure_ascii=False), deal_id),
    )
    db.commit()
    deal = get_deal(db, deal_id)
    assert deal
    out = public_deal(deal)
    if send_offer:
        out["mail"] = _mail_priced_offer(deal)
        out["status"] = "offer_sent"
        db.execute(
            "UPDATE sales_deals SET status='offer_sent', updated_at=datetime('now') WHERE id=?",
            (deal_id,),
        )
        db.commit()
        out = public_deal(get_deal(db, deal_id) or deal)
        out["mail"] = out.get("mail") or _mail_priced_offer(deal)
        out["owner_ping"] = _notify_christian(
            get_deal(db, deal_id) or deal,
            stage="offer_sent",
            db=db,
            extra=f"Setup {setup} € · Monat {monthly} €",
        )
    return out


def _mail_priced_offer(deal: dict[str, Any]) -> dict[str, Any]:
    from email_templates import email_button

    offer = deal.get("offer") or {}
    firma = deal.get("firma") or "Ihr Betrieb"
    name = deal.get("kontakt") or "dort"
    accept = f"{SITE}/sales-angebot.html?d={deal['id']}&accept=1"
    body = f"""
    <p>Hallo {name},</p>
    <p>hier das konkrete Angebot für <strong>{firma}</strong>:</p>
    <p style="font-size:18px;"><strong>{offer.get('name')}</strong><br>
    Setup <strong>{offer.get('setup_eur')} €</strong> · Monat <strong>{offer.get('monthly_eur')} €</strong></p>
    <p>{offer.get('value_promise')}</p>
    <p style="color:#666;font-size:13px;">{offer.get('not_included')}</p>
    <p style="margin:24px 0;">{email_button(accept, "Passt, weiter zur Bestellung")}</p>
    <p>Mit dem Button geht’s weiter zu Vertrag und Zahlung. Fragen einfach zurückmailen.</p>
    <p>Christian · Webschmiede</p>
    """
    text = (
        f"Angebot {firma}: {offer.get('name')} "
        f"Setup {offer.get('setup_eur')} € / Monat {offer.get('monthly_eur')} €\n{accept}\n"
    )
    return _send(deal["email"], f"Angebot {firma} · Webschmiede", body, text)


def accept_and_checkout(db: sqlite3.Connection, deal_id: str) -> dict[str, Any]:
    """Kunde will bestellen → Kunde anlegen falls nötig + Stripe Checkout."""
    deal = get_deal(db, deal_id)
    if not deal:
        return {"ok": False, "error": "Deal unbekannt"}
    if not deal.get("price_setup_eur"):
        _notify_christian(deal, stage="accept_need_price", db=db)
        return {"ok": False, "error": "Zuerst Preis setzen (Christian)", "need_price": True}

    kunde_id = deal.get("kunde_id")
    if not kunde_id:
        kunde_id = _ensure_kunde(deal)
        db.execute(
            "UPDATE sales_deals SET kunde_id=?, updated_at=datetime('now') WHERE id=?",
            (kunde_id, deal_id),
        )
        db.commit()

    package_id = TIER_TO_PACKAGE.get((deal.get("offer") or {}).get("tier") or "beleg", "buchhaltung_beleg")
    try:
        session = _stripe_checkout_for_deal(
            deal,
            kunde_id=kunde_id,
            package_id=package_id,
        )
        url = session.get("url") or ""
        db.execute(
            """
            UPDATE sales_deals
            SET checkout_url=?, status='checkout', updated_at=datetime('now')
            WHERE id=?
            """,
            (url, deal_id),
        )
        db.commit()
        deal = get_deal(db, deal_id)
        assert deal
        mail = _mail_checkout(deal)
        out = public_deal(deal)
        out["checkout"] = session
        out["mail"] = mail
        out["owner_ping"] = _notify_christian(
            deal,
            stage="checkout",
            db=db,
            extra="Zahlungslink liegt beim Kunden. Vertrag (DocuSeal) parallel prüfen.",
        )
        out["contracts_hint"] = (
            "Verträge: DocuSeal Kundenpaket parallel senden "
            "(scripts/send_vertraege_kunde.py oder Agency-Cockpit)."
        )
        return out
    except Exception as e:
        return {"ok": False, "error": str(e)[:240], "kunde_id": kunde_id}


def _stripe_checkout_for_deal(
    deal: dict[str, Any],
    *,
    kunde_id: str,
    package_id: str,
) -> dict[str, Any]:
    """Checkout mit Deal-Preisen (nicht nur Katalog-Defaults)."""
    import stripe
    import stripe_billing as sb

    sb._configure_stripe()  # noqa: SLF001
    setup = int(deal.get("price_setup_eur") or 0) * 100
    monthly = int(deal.get("price_monthly_eur") or 0) * 100
    if setup <= 0 or monthly <= 0:
        raise ValueError("Setup/Monat müssen > 0 sein")
    name = (deal.get("offer") or {}).get("name") or package_id
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer_email=deal.get("email"),
        client_reference_id=kunde_id,
        metadata={
            "kunde_id": kunde_id,
            "package_id": package_id,
            "sales_deal": deal.get("id") or "",
            "shop_name": deal.get("firma") or "",
        },
        subscription_data={
            "metadata": {
                "kunde_id": kunde_id,
                "package_id": package_id,
                "sales_deal": deal.get("id") or "",
            },
        },
        line_items=[
            {
                "price_data": {
                    "currency": "eur",
                    "unit_amount": monthly,
                    "recurring": {"interval": "month"},
                    "product_data": {
                        "name": f"Webschmiede · {name} (Monat)",
                        "description": "Betrieb & Anpassungen",
                    },
                },
                "quantity": 1,
            },
            {
                "price_data": {
                    "currency": "eur",
                    "unit_amount": setup,
                    "product_data": {
                        "name": f"Einrichtung · {name}",
                        "description": "Setup einmalig",
                    },
                },
                "quantity": 1,
            },
        ],
        success_url=f"{SITE}/onboarding?k={kunde_id}&paid=1&deal={deal.get('id')}",
        cancel_url=f"{SITE}/sales-angebot.html?d={deal.get('id')}",
        billing_address_collection="required",
        allow_promotion_codes=True,
    )
    return {"session_id": session.id, "url": session.url, "kunde_id": kunde_id, "package": package_id}


def _mail_checkout(deal: dict[str, Any]) -> dict[str, Any]:
    from email_templates import email_button

    url = deal.get("checkout_url") or "#"
    firma = deal.get("firma") or ""
    body = f"""
    <p>Hallo {deal.get('kontakt') or 'dort'},</p>
    <p>hier der sichere Zahlungslink für <strong>{firma}</strong>.
    Nach der Zahlung bekommt ihr sofort die Zugangsdaten und die nächsten Schritte.</p>
    <p style="margin:24px 0;">{email_button(url, "Jetzt bezahlen")}</p>
    <p>Christian · Webschmiede</p>
    """
    return _send(deal["email"], f"Zahlung · {firma} · Webschmiede", body, f"Zahlen: {url}\n")


def _ensure_kunde(deal: dict[str, Any]) -> str:
    from agency_cockpit import create_kunde

    payload = {
        "name": deal.get("firma") or deal.get("email") or "Neuer Kunde",
        "inhaber": deal.get("kontakt") or "",
        "email": deal.get("email"),
        "telefon": deal.get("phone") or "",
        "branche": "handwerk",
        "kontakt": {
            "email": deal.get("email"),
            "telefon": deal.get("phone") or "",
        },
    }
    try:
        created = create_kunde(payload)
        kid = (
            created.get("id")
            or created.get("kunde_id")
            or (created.get("kunde") or {}).get("id")
            or ""
        )
        if kid:
            return str(kid).upper()
    except Exception:
        pass
    kid = f"WS{deal['id'][:4].upper()}"
    # WS + 4 hex may fail validate – use handwerk suggest via write minimal with SHY-like
    from agency_cockpit import suggest_next_id_for_branche

    try:
        kid = suggest_next_id_for_branche("handwerk")
        create_kunde({**payload, "id": kid})
        return kid.upper()
    except Exception:
        _write_minimal_kunde(kid if kid.startswith("SH") else f"SHY9{deal['id'][:2].upper()}", deal)
        return kid.upper()


def _write_minimal_kunde(kid: str, deal: dict[str, Any]) -> None:
    root = Path(__file__).resolve().parents[2] / "kunden"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{kid}_sales.json"
    data = {
        "id": kid,
        "name": deal.get("firma") or deal.get("email"),
        "inhaber": deal.get("kontakt") or "",
        "kontakt": {"email": deal.get("email"), "telefon": deal.get("phone") or ""},
        "status": "pending",
        "urls": {
            "test_hauptseite": SITE,
            "onboarding_url": f"{SITE}/onboarding?k={kid}",
        },
        "sales_deal": deal.get("id"),
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def meeting_scan(
    db: sqlite3.Connection,
    *,
    website: str = "",
    email: str = "",
    firma: str = "",
    kontakt: str = "",
    phone: str = "",
    note: str = "",
) -> dict[str, Any]:
    """Beim Kunden: Website (+ optional Mail) → Research + Pain-Angebot-Entwurf.

    Kein Auto-Send an den Kunden. Christian sieht Entwurf, kann danach Einladung freigeben.
    """
    ensure_tables(db)
    website = (website or "").strip()
    email = (email or "").strip().lower()
    firma = (firma or "").strip()[:120]
    if not website and not firma:
        return {"ok": False, "error": "Website oder Firmenname nötig"}

    # Firma aus Domain schätzen
    if not firma and website:
        host = re.sub(r"^https?://", "", website, flags=re.I).split("/")[0]
        host = host.replace("www.", "")
        firma = host.split(".")[0].replace("-", " ").title()[:80]

    research = research_company(firma=firma, website=website, tools=[], answers={"wuensche": note})
    try:
        import agency_packages as pkgs

        base = pkgs.PACKAGES.get("buchhaltung_beleg") or {}
        recommended = {
            "tier": "beleg",
            "name": base.get("name") or "Beleg-Pipeline",
            "tagline": base.get("description") or "Belege sortiert statt Chaos",
            "setup_eur": base.get("setup_eur"),
            "monthly_eur": base.get("monthly_eur"),
        }
    except Exception:
        recommended = {"tier": "beleg", "name": "Beleg-Pipeline", "tagline": ""}

    offer = build_pain_offer(research=research, recommended=recommended, with_prices=False)
    deal_id = uuid.uuid4().hex[:12]
    meta = {
        "website": website,
        "meeting_scan_at": _now(),
        "research": research,
        "offer_draft": offer,
        "note": (note or "")[:500],
        "awaiting_freigabe": "invite_or_pain",
    }
    status = "offer_draft" if email else "meeting_scan"
    db.execute(
        """
        INSERT INTO sales_deals (
          id, email, firma, kontakt, phone, product, status, meta_json
        ) VALUES (?, ?, ?, ?, ?, 'buchhaltung', ?, ?)
        """,
        (
            deal_id,
            email or f"pending+{deal_id}@invalid.local",
            firma,
            (kontakt or firma)[:120],
            (phone or "")[:40],
            status,
            json.dumps(meta, ensure_ascii=False),
        ),
    )
    db.commit()
    deal = get_deal(db, deal_id)

    pains = offer.get("pains") or []
    obs = offer.get("observations") or research.get("observations") or []
    lines = [
        f"Meeting-Scan · Deal {deal_id}",
        f"Firma: {firma}",
        f"Website: {website or '–'}",
        f"Mail: {email or '(noch keine – für Einladung brauchen wir eine)'}",
        "",
        "Beobachtungen:",
    ]
    for o in obs[:5]:
        lines.append(f"• {o}")
    lines.append("")
    lines.append("Pain → Lösung (Entwurf):")
    for p in pains[:5]:
        if isinstance(p, dict):
            lines.append(f"• {p.get('label')}: {p.get('solution')}")
    lines.append("")
    lines.append(f"Paket-Vorschlag: {offer.get('name')} ({offer.get('tier')})")
    lines.append(offer.get("price_note") or "")
    lines.append("")
    lines.append(
        "Nächster Schritt: „Einladung senden“ (braucht Mail) oder Preise setzen im Dashboard. "
        "Kein Auto-Mail an den Kunden."
    )
    try:
        _notify_christian(deal or {"id": deal_id, "firma": firma, "email": email}, stage="meeting_scan", db=db)
    except Exception:
        pass
    return {
        "ok": True,
        "deal_id": deal_id,
        "firma": firma,
        "website": website,
        "email": email or None,
        "research": research,
        "offer": offer,
        "text": "\n".join(lines),
        "next": "invite" if email else "need_email",
    }


def website_lead(
    db: sqlite3.Connection,
    *,
    email: str,
    firma: str = "",
    name: str = "",
    phone: str = "",
    message: str = "",
    website: str = "",
    honeypot: str = "",
) -> dict[str, Any]:
    """Öffentlicher Lead von der Website → Invite (ohne Agency-Auth)."""
    if (honeypot or "").strip():
        return {"ok": True, "skipped": True}  # bot
    result = invite(
        db,
        email=email,
        firma=firma,
        kontakt=name,
        phone=phone,
        website=website,
        product="buchhaltung",
        send_email=True,
    )
    deal_id = result.get("id")
    if result.get("ok") and deal_id:
        deal = get_deal(db, deal_id) or {}
        meta = dict(deal.get("meta") or {})
        if message:
            meta["lead_message"] = (message or "")[:500]
        db.execute(
            "UPDATE sales_deals SET meta_json=?, updated_at=datetime('now') WHERE id=?",
            (json.dumps(meta, ensure_ascii=False), deal_id),
        )
        db.commit()
        _notify_christian(get_deal(db, deal_id) or deal, stage="website_lead", db=db)
    return result


def offer_page_data(db: sqlite3.Connection, deal_id: str) -> dict[str, Any]:
    deal = get_deal(db, deal_id)
    if not deal:
        return {"ok": False, "error": "Unbekannt"}
    return public_deal(deal)

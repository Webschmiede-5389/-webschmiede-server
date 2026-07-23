"""Agency Jarvis · Chat pro Kunde (Intents + Aktionen, optional OpenAI)."""
from __future__ import annotations

import json
import os
import re

import agency_cockpit as cockpit
import onboarding as onboarding_svc
import stripe_billing as stripe_svc

KUNDE_RE = re.compile(r"\b(SHY\d{3})\b", re.I)
YES = frozenset({"ja", "yes", "ok", "okay", "bestätigen", "bestaetigen", "senden", "mach", "los"})


def _norm(s: str) -> str:
    s = (s or "").lower().strip()
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"\s+", " ", s)


def _kid(text: str, default: str | None) -> str | None:
    m = KUNDE_RE.search(text or "")
    if m:
        return m.group(1).upper()
    return default.upper() if default else None


def _help_text(kid: str | None) -> str:
    if kid:
        return f"""Jarvis · Kunde **{kid}**{chr(10)}Aktionen gelten für diesen Kunden:

• **Status** / Fortschritt
• **Angebot senden** [starter|pro]
• **Onboarding mail** · **Zahlungslink**
• **Subdomain** [+ SSL] · **Site vorbereiten**
• **Status auf live** / test · **Notiz:** Text

Sage **Ja** zur Bestätigung kritischer Aktionen."""

    return """Jarvis · **Agency-Modus (Global)**

Du bist als **Webschmiede-Inhaber** eingeloggt, **nicht** im Kunden-Account von Hassan Yassine o.ä.

• **Alle Kunden** · Übersicht
• **Status SHY001** · mit Kunden-ID im Text
• Oder oben einen **Kunden wählen** für Aktionen ohne ID

Kunden-Accounts (Bestellportal, Admin) sind getrennt. Hier steuerst du sie nur als Agency."""


def parse_intent(text: str, kunde_id: str | None) -> dict:
    t = _norm(text)
    kid = _kid(text, kunde_id)

    if not t or t in ("hilfe", "help", "?", "was kannst du", "befehle"):
        return {"type": "help"}

    if any(x in t for x in ("alle kunden", "kundenliste", "liste kunden", "wer ist live")):
        return {"type": "list_kunden"}

    if kid and any(x in t for x in ("status", "fortschritt", "wie weit", "stand", "info")):
        if re.search(r"status\s+(auf|setzen|aendern|ändern)\s+(live|test|lead)", t):
            m = re.search(r"(live|test|lead|angebot)", t)
            return {"type": "set_status", "kunde_id": kid, "status": m.group(1) if m else "test"}
        return {"type": "summary", "kunde_id": kid}

    if any(x in t for x in ("angebot", "offer")) and (kid or kunde_id):
        pkg = "starter" if "starter" in t else "pro"
        return {"type": "send_offer", "kunde_id": kid or kunde_id, "package": pkg}

    if any(x in t for x in ("onboarding", "willkommen")) and (kid or kunde_id):
        return {"type": "send_onboarding", "kunde_id": kid or kunde_id}

    if any(x in t for x in ("zahlungslink", "checkout", "stripe", "bezahlen")) and (kid or kunde_id):
        pkg = "starter" if "starter" in t else "pro"
        return {"type": "checkout", "kunde_id": kid or kunde_id, "package": pkg}

    if "subdomain" in t and (kid or kunde_id):
        return {"type": "subdomain", "kunde_id": kid or kunde_id, "ssl": "ssl" in t or "https" in t}

    if any(x in t for x in ("site vorbereiten", "webroot", "static kopieren", "site setup")) and (kid or kunde_id):
        return {"type": "prepare_site", "kunde_id": kid or kunde_id}

    m = re.search(r"notiz\s*[:\-]\s*(.+)", text, re.I | re.S)
    if m and (kid or kunde_id):
        return {"type": "notiz", "kunde_id": kid or kunde_id, "text": m.group(1).strip()[:500]}

    m = re.search(r"status\s+(auf\s+)?(live|test|lead)", t)
    if m and (kid or kunde_id):
        return {"type": "set_status", "kunde_id": kid or kunde_id, "status": m.group(2)}

    if kid:
        return {"type": "summary", "kunde_id": kid}

    return {"type": "unknown", "raw": text}


CONFIRM_ACTIONS = frozenset({
    "send_offer", "send_onboarding", "checkout", "subdomain", "prepare_site", "set_status",
})


def _summary(kid: str) -> str:
    d = cockpit.get_kunde_detail(kid)
    if not d:
        return f"Kunde **{kid}** nicht gefunden."
    pct = (d.get("progress") or {}).get("percent", 0)
    lines = [
        f"**{d.get('name')}** ({kid}) · Status: {d.get('status')}",
        f"Fortschritt: **{pct}%**",
        f"Inhaber: {d.get('inhaber') or '–'} · {(d.get('kontakt') or {}).get('email') or '–'}",
        f"Subdomain: {(d.get('urls') or {}).get('subdomain') or '–'}",
    ]
    open_pts = d.get("open_points") or []
    if open_pts:
        lines.append("Offen: " + "; ".join(open_pts[:4]))
    autos = [a["label"] for a in (d.get("automations") or []) if a.get("active")]
    if autos:
        lines.append("Aktiv: " + ", ".join(autos[:5]))
    return "\n".join(lines)


def _list_kunden() -> str:
    items = cockpit.list_kunden_summary()
    if not items:
        return "Noch keine Kunden angelegt."
    lines = ["**Kunden:**"]
    for k in items:
        lines.append(f"• {k['id']} · {k['name']} ({k.get('status')}, {k.get('progress_percent', 0)}%)")
    return "\n".join(lines)


def _confirm_prompt(intent: dict) -> str:
    kid = intent.get("kunde_id", "")
    t = intent["type"]
    if t == "send_offer":
        return f"Angebot **{intent.get('package', 'pro').upper()}** an **{kid}** senden? Antworte **Ja** oder klicke Bestätigen."
    if t == "send_onboarding":
        return f"Onboarding-Mail an **{kid}** senden? Antworte **Ja**."
    if t == "checkout":
        return f"Stripe-Zahlungslink (**{intent.get('package', 'pro')}**) für **{kid}** erstellen? Antworte **Ja**."
    if t == "subdomain":
        ssl = " mit SSL" if intent.get("ssl") else ""
        return f"Subdomain{ssl} für **{kid}** einrichten? Antworte **Ja**."
    if t == "prepare_site":
        return f"Site/Webroot für **{kid}** vorbereiten? Antworte **Ja**."
    if t == "set_status":
        return f"Status von **{kid}** auf **{intent.get('status')}** setzen? Antworte **Ja**."
    return "Aktion ausführen? Antworte **Ja**."


def execute_intent(intent: dict) -> dict:
    kid = intent.get("kunde_id")
    t = intent["type"]
    try:
        if t == "summary":
            return {"reply": _summary(kid), "actions": []}
        if t == "list_kunden":
            return {"reply": _list_kunden(), "actions": []}
        if t == "help":
            return {"reply": _help_text(kid), "actions": []}
        if t == "send_offer":
            r = cockpit.send_offer(kid, package_id=intent.get("package", "pro"))
            return {"reply": f"Angebot gesendet an **{r['to']}** ({r['package']}).", "actions": []}
        if t == "send_onboarding":
            r = cockpit.send_onboarding(kid)
            return {"reply": f"Onboarding-Mail gesendet an **{r['to']}**.", "actions": []}
        if t == "checkout":
            r = stripe_svc.create_checkout_session(kunde_id=kid, package_id=intent.get("package", "pro"))
            loaded = stripe_svc.load_kunde(kid)
            if loaded:
                k, path = loaded
                k.setdefault("stripe", {})["payment_link"] = r["url"]
                k["stripe"]["status"] = "checkout_offen"
                stripe_svc.save_kunde(k, path)
            return {"reply": f"Zahlungslink erstellt:\n{r['url']}", "actions": [{"type": "open_url", "url": r["url"], "label": "Link öffnen"}]}
        if t == "subdomain":
            r = cockpit.run_subdomain_setup(kid, ssl=bool(intent.get("ssl")))
            if r.get("dry_run"):
                return {"reply": f"Vorschau: {r.get('host')} · {r.get('message', r.get('dns_hint', ''))}", "actions": []}
            return {"reply": f"Subdomain live: **{r.get('url', r.get('host'))}**", "actions": [{"type": "open_url", "url": r.get("url", ""), "label": "Öffnen"}]}
        if t == "prepare_site":
            r = cockpit.run_prepare_site(kid)
            return {"reply": f"Webroot **{r.get('webroot')}** · {r.get('files_copied', 0)} Dateien kopiert.", "actions": []}
        if t == "set_status":
            cockpit.update_kunde(kid, {"status": intent.get("status", "test")})
            return {"reply": f"Status von **{kid}** → **{intent.get('status')}**.", "actions": []}
        if t == "notiz":
            cockpit.update_kunde(kid, {"notiz": intent.get("text", "")})
            return {"reply": f"Notiz für **{kid}** gespeichert.", "actions": []}
    except Exception as e:
        return {"reply": f"Fehler: {str(e)[:200]}", "actions": [], "error": True}
    return {"reply": "Das habe ich nicht verstanden. Sage **Hilfe** für Befehle.", "actions": []}


def _try_llm(
    message: str,
    kunde_id: str | None,
    *,
    persona: str = "jarvis",
    history: list[dict] | None = None,
) -> tuple[str | None, str | None, str | None]:
    """Returns (reply, error_code, provider). Nutzt Ollama (gratis) zuerst, optional OpenAI."""
    import llm_client as llm

    ctx = ""
    if kunde_id:
        ob = onboarding_svc.build_onboarding(kunde_id)
        if ob:
            ctx = (
                f"Aktueller Kundenkontext: {ob.get('name')} ({kunde_id}), "
                f"Status {ob.get('status')}, Fortschritt {ob.get('progress', {}).get('percent')}%."
            )

    if persona == "nils":
        import human_voice as voice

        system = voice.nils_system(
            "Themen: Server, Deploy, Portale, Funnel, Buchhaltung, Domains, Watchdogs, Sales. "
            "Normale Betriebsfragen nie abweisen. "
            "Für Logos/Bilder/Instagram-Visuals nutzt das System Requesty automatisch. "
            "Video erzeugen geht über Requesty noch nicht. "
            "Schreib so, dass Christian das Gefühl hat, mit einem echten Kollegen zu chatten.\n"
            + ctx
        )
        max_tokens = 900
        temperature = 0.7
        timeout = 90
    else:
        system = (
            "Du bist Jarvis bei Webschmiede. Antworte kurz auf Deutsch, menschlich, "
            "ohne Agentur-Ton. Kunden-Onboarding, Angebote, Subdomains. "
            "Keine erfundenen URLs.\n"
            + ctx
        )
        max_tokens = 400
        temperature = 0.55
        timeout = 45

    messages: list[dict] = [{"role": "system", "content": system}]
    for h in (history or [])[-12:]:
        role = h.get("role") or ""
        body = (h.get("body") or "").strip()
        if not body:
            continue
        if role in ("assistant", "bot"):
            messages.append({"role": "assistant", "content": body[:1500]})
        elif role == "user":
            messages.append({"role": "user", "content": body[:1500]})
    messages.append({"role": "user", "content": message[:3500]})

    # Nils: bei vorhandenem Requesty-Key Cloud-Qualität bevorzugen (Dispatcher nutzt Primary)
    result = llm.chat(
        messages,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
        route="A" if persona == "nils" else None,
    )
    if result.get("ok") and result.get("reply"):
        return result["reply"], None, result.get("provider")
    return None, result.get("error") or "llm_fail", result.get("provider")


def handle_chat(
    message: str,
    *,
    kunde_id: str | None = None,
    confirm: bool = False,
    pending: dict | None = None,
    persona: str = "jarvis",
    history: list[dict] | None = None,
) -> dict:
    text = (message or "").strip()
    kid = kunde_id.upper() if kunde_id else None

    if pending and (confirm or _norm(text) in YES):
        result = execute_intent(pending)
        result["pending"] = None
        result["needs_confirm"] = False
        return result

    if pending and not confirm:
        return {
            "reply": "Noch eine Aktion offen. **Ja** zum Bestätigen oder **Abbrechen**.",
            "pending": pending,
            "needs_confirm": True,
            "actions": [{"type": "confirm", "label": "Bestätigen"}, {"type": "cancel", "label": "Abbrechen"}],
        }

    if _norm(text) in ("abbrechen", "cancel", "stop", "nein"):
        return {"reply": "Abgebrochen.", "pending": None, "needs_confirm": False, "actions": []}

    intent = parse_intent(text, kid)

    # Nils: freies Gespräch / Hilfe über LLM; echte Aktionen (Status SHY001 …) bleiben Befehle
    prefer_llm = persona == "nils" and intent["type"] in ("unknown", "help")
    if intent["type"] == "unknown" or prefer_llm:
        ai, err, provider = _try_llm(text, kid, persona=persona, history=history)
        if ai:
            return {
                "reply": ai,
                "actions": [],
                "pending": None,
                "needs_confirm": False,
                "llm_provider": provider,
            }
        if persona == "nils":
            if err == "missing_key":
                reply = (
                    "Gerade komme ich nicht richtig zum Denken (kein LLM). "
                    "Ollama auf auto-01 prüfen, optional OpenAI-Key. "
                    "Kurz geht trotzdem: Alle Kunden, Status SHY001."
                )
            else:
                reply = (
                    "Kurz hängt was am LLM. Versuch in einer Minute nochmal, "
                    "oder Kurzbefehl: Alle Kunden / Status SHY001."
                )
            return {
                "reply": reply,
                "actions": [
                    {"type": "quick", "message": "Alle Kunden", "label": "Kunden"},
                    {"type": "quick", "message": "Status SHY001", "label": "SHY001"},
                ],
                "pending": None,
                "needs_confirm": False,
                "llm_error": err,
            }
        return {
            "reply": "Das habe ich nicht erkannt. " + _help_text(kid),
            "actions": [{"type": "quick", "message": "Hilfe", "label": "Hilfe"}],
            "pending": None,
            "needs_confirm": False,
        }

    if intent["type"] == "help":
        return {"reply": _help_text(kid), "actions": _quick_actions(kid), "pending": None, "needs_confirm": False}

    if intent["type"] in CONFIRM_ACTIONS:
        return {
            "reply": _confirm_prompt(intent),
            "pending": intent,
            "needs_confirm": True,
            "actions": [{"type": "confirm", "label": "Bestätigen"}, {"type": "cancel", "label": "Abbrechen"}],
        }

    result = execute_intent(intent)
    result["pending"] = None
    result["needs_confirm"] = False
    if not result.get("actions"):
        result["actions"] = _quick_actions(kid)
    return result


def _quick_actions(kid: str | None) -> list[dict]:
    if not kid:
        return [
            {"type": "quick", "message": "Alle Kunden", "label": "Kunden"},
            {"type": "quick", "message": "Hilfe", "label": "Hilfe"},
        ]
    return [
        {"type": "quick", "message": "Status", "label": "Status"},
        {"type": "quick", "message": "Angebot senden", "label": "Angebot"},
        {"type": "quick", "message": "Subdomain SSL", "label": "Subdomain"},
        {"type": "quick", "message": "Hilfe", "label": "Hilfe"},
    ]


def log_message(db, *, kunde_id: str | None, role: str, body: str, meta: dict | None = None) -> None:
    db.execute(
        """INSERT INTO agency_chat (kunde_id, role, body, meta) VALUES (?,?,?,?)""",
        (kunde_id or "", role, body[:4000], json.dumps(meta or {}, ensure_ascii=False)),
    )


def get_history(db, kunde_id: str | None = None, limit: int = 40) -> list[dict]:
    if kunde_id:
        rows = db.execute(
            """SELECT id, kunde_id, role, body, meta, created_at FROM agency_chat
               WHERE kunde_id=? ORDER BY id DESC LIMIT ?""",
            (kunde_id.upper(), limit),
        ).fetchall()
    else:
        rows = db.execute(
            """SELECT id, kunde_id, role, body, meta, created_at FROM agency_chat
               WHERE kunde_id IS NULL OR kunde_id = '' ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    out = []
    for r in reversed(rows):
        d = dict(r)
        try:
            d["meta"] = json.loads(d.get("meta") or "{}")
        except json.JSONDecodeError:
            d["meta"] = {}
        out.append(d)
    return out

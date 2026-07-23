"""Agency cockpit · Kunden, Angebote, Onboarding-Aktionen."""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import onboarding as onboarding_svc
from agency_mail import send_html_email
from agency_packages import AGENCY_LEGAL, PACKAGES
from email_templates import email_shell
from stripe_billing import load_kunde, save_kunde

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import kunden_ids as kid_svc

KUNDEN_DIR = Path(os.getenv("KUNDEN_DIR", Path(__file__).resolve().parents[1] / "kunden"))
DOMAIN = "digitalehandwerkskunst.de"
SERVER_IP = os.getenv("SERVER_IP", "167.233.211.170")

DEFAULT_CLIENT_AUTOMATIONS = {
    "sms": {"label": "SMS Bestellbenachrichtigung", "requested": True},
    "review": {"label": "Google-Review Funnel", "requested": True},
    "n8n_orders": {"label": "n8n Bestell-Alerts", "requested": True},
    "followups": {"label": "Follow-up Workflows", "requested": False},
    "loyalty": {"label": "Bonuskarte / Treue", "requested": True},
}

VOICE_PROVIDERS = ("", "retell", "vapi", "elevenlabs", "other")
VOICE_BILLING_PLANS = ("none", "included", "per_minute", "bundle")


def _pack_for_branche(branche: str) -> str:
    b = (branche or "").strip().lower()
    if b in ("restaurant", "gastro"):
        return "gastro"
    if b in ("handwerk", "dach", "dental", "friseur"):
        return "handwerk"
    return "general"


def default_sms(overrides: dict | None = None) -> dict:
    base = {
        "enabled": False,
        "provider": "seven.io",
        "phone_number": "",
        "sender_id": "",
        "owner_phone": "",
        "notes": "",
    }
    if not overrides:
        return base
    return {**base, **{k: overrides[k] for k in base if k in overrides}}


def default_whatsapp(overrides: dict | None = None) -> dict:
    base = {
        "enabled": False,
        "phone_number_id": "",
        "waba_id": "",
        "business_phone": "",
        "access_token": "",
        "access_token_env": "",
        "allowed_phones": [],
        "permissions": ["menu_price", "menu_text", "menu_image", "menu_available"],
        "blocked": ["code", "domain", "admin_password", "delete_items"],
    }
    if not overrides:
        return base
    merged = {**base, **{k: overrides[k] for k in overrides if k in base or k in ("allowed_phones", "permissions", "blocked")}}
    for list_key in ("allowed_phones", "permissions", "blocked"):
        if list_key in overrides and isinstance(overrides[list_key], list):
            merged[list_key] = [str(x).strip() for x in overrides[list_key] if str(x).strip()]
    return merged


def default_voice(branche: str = "restaurant", overrides: dict | None = None) -> dict:
    pack = _pack_for_branche(branche)
    base = {
        "enabled": False,
        "provider": "",
        "agent_id": "",
        "phone_number": "",
        "knowledge_pack": pack,
        "billing": {
            "plan": "none",
            "included_minutes": 0,
            "overage_per_min_eur": 0.0,
        },
    }
    if not overrides:
        return base
    billing = {**base["billing"], **(overrides.get("billing") or {})}
    merged = {**base, **{k: overrides[k] for k in overrides if k != "billing"}}
    merged["billing"] = billing
    if merged.get("provider") and merged["provider"] not in VOICE_PROVIDERS:
        merged["provider"] = "other"
    if billing.get("plan") not in VOICE_BILLING_PLANS:
        billing["plan"] = "none"
    return merged


def default_knowledge(branche: str = "restaurant", overrides: dict | None = None) -> dict:
    pack = _pack_for_branche(branche)
    base = {
        "pack": pack,
        "locale": "de-DE",
        "overrides": {},
        "voice": {"enabled": False, "provider": "", "voice_id": ""},
    }
    if not overrides:
        return base
    merged = {**base, **{k: overrides[k] for k in overrides if k != "voice"}}
    if overrides.get("voice"):
        merged["voice"] = {**base["voice"], **overrides["voice"]}
    if overrides.get("overrides") is not None:
        merged["overrides"] = overrides["overrides"] if isinstance(overrides["overrides"], dict) else {}
    return merged


def list_knowledge_packs() -> list[dict]:
    env = os.getenv("KNOWLEDGE_DIR", "").strip()
    candidates = []
    if env:
        candidates.append(Path(env))
    # Server: /root/app/knowledge · lokal: Repo/knowledge oder app/knowledge
    candidates.append(ROOT / "knowledge")
    candidates.append(Path(__file__).resolve().parents[1] / "knowledge")
    candidates.append(Path(__file__).resolve().parents[2] / "knowledge")
    packs_dir = None
    for base in candidates:
        p = base / "packs" if base.name != "packs" else base
        if not str(base).endswith("packs"):
            p = base / "packs"
        else:
            p = base
        if p.is_dir():
            packs_dir = p
            break
    items = []
    if not packs_dir:
        return [{"id": "gastro", "label": "Gastronomie"}, {"id": "handwerk", "label": "Handwerk"}, {"id": "general", "label": "Allgemein"}]
    for p in sorted(packs_dir.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            items.append({"id": data.get("id") or p.stem, "label": data.get("label") or p.stem})
        except Exception:
            items.append({"id": p.stem, "label": p.stem})
    return items or [{"id": "general", "label": "Allgemein"}]


def _channel_readiness() -> dict:
    sms_key = bool(os.getenv("SMS_API_KEY", "").strip())
    wa_token = bool(os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip())
    return {
        "sms": {
            "agency_ready": sms_key,
            "hint": "seven.io Key in Agency Setup hinterlegen" if not sms_key else "Agency SMS-Key vorhanden",
        },
        "whatsapp": {
            "agency_ready": wa_token,
            "hint": "Meta WhatsApp Token in .env" if not wa_token else "WhatsApp Token vorhanden",
        },
        "voice": {
            "agency_ready": True,
            "hint": "Provider-Keys folgen mit Voice-Anbindung",
        },
    }


def build_channels_view(k: dict) -> dict:
    branche = k.get("branche") or "restaurant"
    sms = default_sms(k.get("sms") or {})
    # Legacy: crm.sms_enabled / n8n.owner_phone
    crm = k.get("crm") or {}
    if not k.get("sms") and crm.get("sms_enabled"):
        sms["enabled"] = True
    n8n = k.get("n8n") or {}
    if not sms.get("owner_phone") and n8n.get("owner_phone"):
        sms["owner_phone"] = n8n["owner_phone"]
    wa = default_whatsapp(k.get("whatsapp") or {})
    voice = default_voice(branche, k.get("voice") or {})
    kn = default_knowledge(branche, k.get("knowledge") or {})
    if not voice.get("knowledge_pack"):
        voice["knowledge_pack"] = kn.get("pack") or _pack_for_branche(branche)
    ready = _channel_readiness()
    return {
        "sms": {**sms, "agency_ready": ready["sms"]["agency_ready"], "agency_hint": ready["sms"]["hint"]},
        "whatsapp": {**wa, "agency_ready": ready["whatsapp"]["agency_ready"], "agency_hint": ready["whatsapp"]["hint"]},
        "voice": {**voice, "agency_ready": ready["voice"]["agency_ready"], "agency_hint": ready["voice"]["hint"]},
        "knowledge": kn,
        "packs": list_knowledge_packs(),
        "voice_providers": [p for p in VOICE_PROVIDERS if p],
        "voice_billing_plans": list(VOICE_BILLING_PLANS),
    }


def _default_integrations(kid: str, overrides: dict | None = None) -> dict:
    base = {
        "buchhaltung": "",
        "lexware": {
            "enabled": False,
            "sync_contacts": True,
            "sync_invoices": False,
            "api_key_env": f"LEXWARE_API_KEY_{kid}",
        },
    }
    if not overrides:
        return base
    merged = {**base, **overrides}
    if overrides.get("lexware"):
        merged["lexware"] = {**base["lexware"], **overrides["lexware"]}
    return merged


def suggest_next_id(prefix: str = "SHY") -> str:
    return kid_svc.suggest_next_id(KUNDEN_DIR, prefix)


def suggest_next_id_for_branche(branche: str) -> str:
    return kid_svc.suggest_next_id_for_branche(KUNDEN_DIR, branche)


def list_id_prefixes() -> list[dict]:
    return kid_svc.list_prefixes()


def prefix_for_branche(branche: str) -> str:
    return kid_svc.prefix_for_branche(branche)


def _slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "kunde"


def list_kunden_summary() -> list[dict]:
    items = []
    if not KUNDEN_DIR.is_dir():
        return items
    for p in sorted(KUNDEN_DIR.glob("*.json")):
        k = json.loads(p.read_text(encoding="utf-8"))
        ob = onboarding_svc.build_onboarding(k.get("id", ""))
        prog = (ob or {}).get("progress") or {}
        items.append({
            "id": k.get("id"),
            "name": k.get("name"),
            "inhaber": k.get("inhaber"),
            "status": k.get("status"),
            "branche": k.get("branche"),
            "email": (k.get("kontakt") or {}).get("email"),
            "telefon": (k.get("kontakt") or {}).get("telefon"),
            "progress_percent": prog.get("percent", 0),
            "billing": k.get("billing") or {},
            "stripe_status": (k.get("stripe") or {}).get("status"),
            "stripe_link": (k.get("stripe") or {}).get("payment_link"),
            "erstellt": k.get("erstellt"),
        })
    return items


def get_kunde_detail(kid: str) -> dict | None:
    loaded = load_kunde(kid)
    if not loaded:
        return None
    k, path = loaded
    ob = onboarding_svc.build_onboarding(kid)
    if not ob:
        return None

    env = onboarding_svc._env_flags()
    try:
        import client_setup as setup_svc
        global_auto = setup_svc.global_automation_status()
    except Exception:
        global_auto = {}

    client_auto = k.get("automations") or {}
    automations = _build_automations(env, global_auto, client_auto)

    history = list((k.get("agency_history") or []))
    history.reverse()

    return {
        **ob,
        "slug": k.get("slug"),
        "kontakt": k.get("kontakt"),
        "billing": k.get("billing") or {},
        "stripe": k.get("stripe") or {},
        "automations": automations,
        "global_automations": global_auto,
        "server": k.get("server") or {},
        "integrations": k.get("integrations") or {},
        "channels": build_channels_view(k),
        "subdomain": (k.get("urls") or {}).get("subdomain", ""),
        "packages": [{k: v for k, v in p.items() if not k.endswith("_cents")} for p in PACKAGES.values()],
        "history": history[:20],
        "json_path": path.name,
    }


def create_kunde(data: dict) -> dict:
    name = (data.get("name") or "").strip()
    branche = (data.get("branche") or "restaurant").strip()
    kid = (data.get("id") or "").upper().strip()
    if not kid:
        kid = suggest_next_id_for_branche(branche)
    if not name:
        raise ValueError("name ist Pflicht")
    if not kid_svc.validate_kunde_id(kid):
        raise ValueError(f"Ungueltige Kunden-ID: {kid} (Format: SHY001)")

    if load_kunde(kid):
        raise ValueError(f"Kunde {kid} existiert bereits")

    slug = _slugify(data.get("slug") or name)
    subdomain = _slugify(data.get("subdomain") or slug)[:24]
    inhaber = (data.get("inhaber") or "").strip()
    kontakt = data.get("kontakt") or {}
    telefon = (kontakt.get("telefon") or data.get("telefon") or "").strip()
    email = (kontakt.get("email") or data.get("email") or "").strip()
    adresse = (kontakt.get("adresse") or data.get("adresse") or "").strip()

    base = f"https://{subdomain}.{DOMAIN}"
    k = {
        "id": kid,
        "name": name,
        "inhaber": inhaber,
        "slug": slug,
        "branche": branche,
        "erstellt": date.today().isoformat(),
        "status": "lead",
        "kontakt": {"telefon": telefon, "email": email, "adresse": adresse},
        "urls": {
            "subdomain": subdomain,
            "demo_url": f"https://muster.{DOMAIN}/",
            "onboarding_url": f"{base}/onboarding?k={kid}",
            "test_hauptseite": f"{base}/",
            "test_bestellen": f"{base}/bestellen",
            "test_admin": f"{base}/admin",
            "domain": "",
            "live_hauptseite": "",
            "live_bestellen": "",
        },
        "server": {
            "ip": SERVER_IP,
            "ordner": f"/var/www/{slug}",
            "service": "snack-api",
            "port": "8000",
        },
        "crm": {"provider": "webschmiede", "sms_provider": "seven.io", "sms_enabled": False},
        "sms": default_sms({"owner_phone": telefon}),
        "whatsapp": default_whatsapp(),
        "voice": default_voice(branche),
        "knowledge": default_knowledge(branche),
        "automations": {k: dict(v) for k, v in DEFAULT_CLIENT_AUTOMATIONS.items()},
        "stripe": {"status": "ausstehend", "payment_link": ""},
        "billing": {},
        "n8n": {
            "order_webhook": kid_svc.n8n_order_webhook(kid),
        },
        "buchhaltung": {
            "bookkeeper_email": (data.get("buchhaltung") or {}).get("bookkeeper_email", "").strip(),
        },
        "integrations": _default_integrations(kid, data.get("integrations")),
        "domain": {
            "status": "open",
            "selected": "",
            "wish": "",
            "options": [],
        },
        "google": {
            "status": "open",
            "review_url": "",
            "owner_email": email,
            "place_id": "",
            "location_name": name,
            "manager_invited": False,
            "oauth_connected": False,
            "auto_reply_enabled": False,
            "notes": "",
        },
        "offene_punkte": [
            "Angebot senden & Freigabe einholen",
            "Subdomain/DNS einrichten",
            "Testbestellung durchführen",
            "SMS + Google Review (optional)",
            f"n8n-Workflows für {kid} anlegen",
        ],
        "agency_history": [],
    }

    from client_brand import default_gastro_brand, is_gastro

    if is_gastro(branche):
        k["brand"] = default_gastro_brand(slug=slug, name=name)
        k["offene_punkte"].insert(
            3,
            "Logo unter /brand/{slug}-logo.png legen + Tischaufsteller drucken".replace("{slug}", slug),
        )
        k["offene_punkte"].insert(4, "Tisch-QR: 5 %-Aktion im Admin anlegen")
    else:
        k["brand"] = data.get("brand") or {}

    if data.get("brand"):
        k["brand"] = data["brand"]

    KUNDEN_DIR.mkdir(parents=True, exist_ok=True)
    path = KUNDEN_DIR / f"{kid}_{slug}.json"
    save_kunde(k, path)
    _log_history(k, path, "kunde_angelegt", f"Kunde {kid} im Dashboard angelegt")

    n8n_result = None
    n8n_error = None
    try:
        from n8n_kunde import provision_kunde

        n8n_result = provision_kunde(kid)
        k["n8n"] = n8n_result.get("n8n") or k.get("n8n")
        save_kunde(k, path)
        _log_history(k, path, "n8n_provisioniert", ", ".join(n8n_result.get("workflows") or []))
        k["offene_punkte"] = [x for x in k.get("offene_punkte", []) if "n8n-Workflows" not in x]
        save_kunde(k, path)
    except Exception as e:
        n8n_error = str(e)[:200]

    out = {"id": kid, "path": path.name, "n8n": n8n_result}
    if n8n_error:
        out["n8n_error"] = n8n_error
    return out


def update_kunde(kid: str, patch: dict) -> dict:
    loaded = load_kunde(kid)
    if not loaded:
        raise ValueError("Kunde nicht gefunden")
    k, path = loaded

    if "status" in patch and patch["status"]:
        old = k.get("status")
        k["status"] = str(patch["status"]).strip()
        if old != k["status"]:
            _log_history(k, path, "status_geaendert", f"{old} → {k['status']}")
    if "offene_punkte" in patch and isinstance(patch["offene_punkte"], list):
        k["offene_punkte"] = [str(x).strip() for x in patch["offene_punkte"] if str(x).strip()]
        _log_history(k, path, "offene_punkte", "Checkliste aktualisiert")
    if "notiz" in patch and patch["notiz"]:
        text = str(patch["notiz"]).strip()
        k.setdefault("notizen", []).append({
            "at": date.today().isoformat(),
            "text": text,
        })
        _log_history(k, path, "notiz", text)

    save_kunde(k, path)
    return {"ok": True, "id": kid}


def update_channels(kid: str, data: dict) -> dict:
    """SMS / WhatsApp / Voice / Knowledge pro Kunde speichern."""
    loaded = load_kunde(kid)
    if not loaded:
        raise ValueError("Kunde nicht gefunden")
    k, path = loaded
    branche = k.get("branche") or "restaurant"
    changed: list[str] = []

    if "sms" in data and isinstance(data["sms"], dict):
        sms = default_sms({**(k.get("sms") or {}), **data["sms"]})
        sms["enabled"] = bool(data["sms"].get("enabled", sms["enabled"]))
        for key in ("phone_number", "sender_id", "owner_phone", "notes", "provider"):
            if key in data["sms"]:
                sms[key] = str(data["sms"].get(key) or "").strip()
        k["sms"] = sms
        k.setdefault("crm", {})["sms_enabled"] = sms["enabled"]
        k.setdefault("crm", {})["sms_provider"] = sms.get("provider") or "seven.io"
        if sms.get("owner_phone"):
            k.setdefault("n8n", {})["owner_phone"] = sms["owner_phone"]
        # Sync automation toggle
        k.setdefault("automations", {})
        entry = dict(k["automations"].get("sms") or DEFAULT_CLIENT_AUTOMATIONS["sms"])
        entry["requested"] = sms["enabled"]
        k["automations"]["sms"] = entry
        changed.append("sms")

    if "whatsapp" in data and isinstance(data["whatsapp"], dict):
        wa_in = data["whatsapp"]
        wa = default_whatsapp({**(k.get("whatsapp") or {}), **wa_in})
        wa["enabled"] = bool(wa_in.get("enabled", wa["enabled"]))
        for key in ("phone_number_id", "business_phone"):
            if key in wa_in:
                wa[key] = str(wa_in.get(key) or "").strip()
        if "allowed_phones" in wa_in:
            raw = wa_in["allowed_phones"]
            if isinstance(raw, str):
                phones = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
            elif isinstance(raw, list):
                phones = [str(p).strip() for p in raw if str(p).strip()]
            else:
                phones = wa.get("allowed_phones") or []
            wa["allowed_phones"] = phones
        k["whatsapp"] = wa
        changed.append("whatsapp")

    if "voice" in data and isinstance(data["voice"], dict):
        v_in = data["voice"]
        voice = default_voice(branche, {**(k.get("voice") or {}), **v_in})
        voice["enabled"] = bool(v_in.get("enabled", voice["enabled"]))
        for key in ("provider", "agent_id", "phone_number", "knowledge_pack"):
            if key in v_in:
                voice[key] = str(v_in.get(key) or "").strip()
        if "billing" in v_in and isinstance(v_in["billing"], dict):
            bill = {**voice["billing"], **v_in["billing"]}
            bill["plan"] = str(bill.get("plan") or "none")
            if bill["plan"] not in VOICE_BILLING_PLANS:
                bill["plan"] = "none"
            try:
                bill["included_minutes"] = int(bill.get("included_minutes") or 0)
            except (TypeError, ValueError):
                bill["included_minutes"] = 0
            try:
                bill["overage_per_min_eur"] = float(bill.get("overage_per_min_eur") or 0)
            except (TypeError, ValueError):
                bill["overage_per_min_eur"] = 0.0
            voice["billing"] = bill
        k["voice"] = voice
        # Keep knowledge.pack in sync for Bot/Voice
        kn = default_knowledge(branche, k.get("knowledge") or {})
        if voice.get("knowledge_pack"):
            kn["pack"] = voice["knowledge_pack"]
        kn.setdefault("voice", {})
        kn["voice"]["enabled"] = voice["enabled"]
        kn["voice"]["provider"] = voice.get("provider") or ""
        kn["voice"]["voice_id"] = voice.get("agent_id") or kn["voice"].get("voice_id") or ""
        k["knowledge"] = kn
        changed.append("voice")

    if "knowledge" in data and isinstance(data["knowledge"], dict):
        kn_in = data["knowledge"]
        kn = default_knowledge(branche, {**(k.get("knowledge") or {}), **kn_in})
        if "pack" in kn_in:
            kn["pack"] = str(kn_in.get("pack") or "general").strip() or "general"
        k["knowledge"] = kn
        if k.get("voice"):
            k["voice"]["knowledge_pack"] = kn["pack"]
        changed.append("knowledge")

    if not changed:
        raise ValueError("Keine Kanal-Daten zum Speichern")

    _log_history(k, path, "channels_updated", ", ".join(changed))
    save_kunde(k, path)
    return {"ok": True, "id": kid, "channels": build_channels_view(k), "changed": changed}


def _log_history(k: dict, path: Path, action: str, detail: str) -> None:
    from datetime import datetime, timezone

    k.setdefault("agency_history", []).append({
        "at": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "detail": detail,
    })
    save_kunde(k, path)


def _offer_body(k: dict, pkg: dict, note: str) -> tuple[str, str, str]:
    name = k.get("inhaber") or k.get("name", "")
    shop = k["name"]
    setup = pkg["setup_eur"]
    monthly = pkg["monthly_eur"]
    subject = f"Angebot: {pkg['name']} für {shop}"

    text = f"""Hallo {name},

anbei unser Angebot für {shop}:

Paket: {pkg['name']}
Einmalig: {setup:,} €
Optional monatlich: {monthly:,} €/Monat

{pkg['description']}

{note}

Freue mich auf Ihre Rückmeldung.

{AGENCY_LEGAL['owner']}
Webschmiede · Digitale Handwerkskunst
{AGENCY_LEGAL['email']}
""".replace(",", ".")

    note_html = f"<p><em>{note}</em></p>" if note else ""
    body = f"""
    <p>Guten Tag {name},</p>
    <p>für <strong>{shop}</strong> haben wir folgendes Paket zusammengestellt:</p>
    <table role="presentation" width="100%" style="background:#FFF4ED;border-radius:10px;border:1px solid #FFD4B8;margin:16px 0;">
      <tr><td style="padding:16px 18px;">
        <p style="margin:0 0 6px;color:#FF6600;font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;">{pkg['name']}</p>
        <p style="margin:0 0 8px;font-size:22px;font-weight:700;color:#1A1A1A;">{setup:,} € <span style="font-size:14px;font-weight:400;color:#666;">einmalig</span></p>
        <p style="margin:0;font-size:14px;color:#444;">Optional: <strong>{monthly:,} €/Monat</strong> Wartung & Support</p>
        <p style="margin:12px 0 0;font-size:13px;color:#666;">{pkg['description']}</p>
      </td></tr>
    </table>
    {note_html}
    <p>PDF-Angebot auf Wunsch, oder wir besprechen alles kurz telefonisch.</p>
    <p style="font-size:13px;color:#888;">{AGENCY_LEGAL['vat_note']}</p>
    """.replace(",", ".")

    html = email_shell(
        hero_title=f"Angebot für {shop}",
        hero_subtitle=pkg["name"],
        preheader=f"Setup {setup} € · {pkg['description'][:60]}",
        body_html=body,
    )
    return subject, text, html


def send_offer(kid: str, *, package_id: str, note: str = "", email: str | None = None) -> dict:
    loaded = load_kunde(kid)
    if not loaded:
        raise ValueError("Kunde nicht gefunden")
    k, path = loaded
    pkg = PACKAGES.get(package_id)
    if not pkg:
        raise ValueError("Unbekanntes Paket")

    to = (email or (k.get("kontakt") or {}).get("email") or "").strip()
    if not to:
        raise ValueError("Keine E-Mail-Adresse für den Kunden")

    subject, text, html = _offer_body(k, pkg, note.strip())
    send_html_email(to=to, subject=subject, html=html, text=text)

    if k.get("status") in ("lead", "neu"):
        k["status"] = "angebot_gesendet"
    _log_history(k, path, "angebot_gesendet", f"{pkg['name']} an {to}")
    return {"ok": True, "to": to, "package": package_id}


def send_onboarding(kid: str, *, email: str | None = None) -> dict:
    loaded = load_kunde(kid)
    if not loaded:
        raise ValueError("Kunde nicht gefunden")
    k, path = loaded
    ob = onboarding_svc.build_onboarding(kid)
    if not ob:
        raise ValueError("Onboarding-Daten fehlen")

    to = (email or (k.get("kontakt") or {}).get("email") or "").strip()
    if not to:
        raise ValueError("Keine E-Mail-Adresse")

    name = k.get("inhaber") or k.get("name", "")
    shop = k["name"]
    onboarding_url = ob["urls"].get("onboarding") or ""
    subject = f"Willkommen: Ihr Onboarding für {shop}"

    text = f"""Hallo {name},

Ihr Webschmiede-System für {shop} ist bereit.

Onboarding-Portal (Links & Checkliste):
{onboarding_url}

Admin-Passwort erhalten Sie separat.

Viele Grüße
Webschmiede
"""

    body = f"""
    <p>Guten Tag {name},</p>
    <p>Ihr System für <strong>{shop}</strong> steht bereit. Fortschritt: <strong>{ob['progress']['percent']}%</strong>.</p>
    {"<p style='text-align:center;margin:24px 0;'><a href='" + onboarding_url + "' style='display:inline-block;background:#FF6600;color:#fff;font-weight:700;padding:14px 28px;border-radius:10px;text-decoration:none;'>Onboarding öffnen</a></p>" if onboarding_url else ""}
    <p>Admin-Passwort erhalten Sie separat (nicht per E-Mail).</p>
    """
    html = email_shell(
        hero_title=f"Onboarding · {shop}",
        hero_subtitle="Links, Checkliste, nächste Schritte",
        preheader=f"Onboarding für {shop}",
        body_html=body,
    )
    send_html_email(to=to, subject=subject, html=html, text=text)
    _log_history(k, path, "onboarding_gesendet", f"An {to}")
    return {"ok": True, "to": to}


def _build_automations(env: dict, global_auto: dict, client_auto: dict) -> list[dict]:
    defs = [
        ("sms", "SMS Bestellbenachrichtigung", env["sms_enabled"] and env["sms_key"] and env["owner_phone"], "seven.io + OWNER_PHONE"),
        ("review", "Google-Review nach Bestellung", env["google_review"], "GOOGLE_REVIEW_URL"),
        ("n8n_orders", "n8n Bestell-Alerts", env["n8n_orders"], "N8N_ORDER_WEBHOOK"),
        ("inbox_agent", "E-Mail-Agent (Posteingang)", bool(global_auto.get("inbox", {}).get("active")), "IONOS IMAP → n8n"),
        ("followups", "Follow-up Workflows", False, "n8n Workflow importieren"),
        ("loyalty", "Bonuskarte / Treue", True, "Loyalty-Modul aktiv"),
    ]
    out = []
    for aid, label, server_ok, hint in defs:
        cfg = client_auto.get(aid) or DEFAULT_CLIENT_AUTOMATIONS.get(aid, {})
        requested = cfg.get("requested", True)
        out.append({
            "id": aid,
            "label": cfg.get("label") or label,
            "requested": requested,
            "server_ready": server_ok,
            "active": server_ok and requested,
            "owner": "webschmiede",
            "hint": hint,
        })
    return out


def get_global_automations() -> dict:
    try:
        import client_setup as setup_svc
        return setup_svc.global_automation_status()
    except Exception as e:
        return {"error": str(e)[:120]}


def update_client_automation(kid: str, automation_id: str, *, requested: bool) -> dict:
    loaded = load_kunde(kid)
    if not loaded:
        raise ValueError("Kunde nicht gefunden")
    k, path = loaded
    k.setdefault("automations", {})
    entry = dict(k["automations"].get(automation_id) or DEFAULT_CLIENT_AUTOMATIONS.get(automation_id, {}))
    entry["requested"] = requested
    k["automations"][automation_id] = entry
    if automation_id == "sms":
        k.setdefault("crm", {})["sms_enabled"] = requested
    _log_history(k, path, "automation", f"{automation_id}: {'an' if requested else 'aus'}")
    save_kunde(k, path)
    return {"ok": True, "id": automation_id, "requested": requested}


def run_subdomain_setup(kid: str, *, ssl: bool = False) -> dict:
    import client_setup as setup_svc
    if not load_kunde(kid):
        raise ValueError("Kunde nicht gefunden")
    result = setup_svc.setup_subdomain(kid, ssl=ssl)
    if result.get("ok"):
        loaded = load_kunde(kid)
        if loaded:
            k, path = loaded
            detail = f"{result.get('host')} SSL={result.get('ssl', False)}"
            _log_history(k, path, "subdomain", detail)
            if k.get("status") == "lead":
                k["status"] = "test"
                save_kunde(k, path)
    elif not result.get("dry_run"):
        raise RuntimeError(result.get("message", "Subdomain fehlgeschlagen"))
    return result


def run_prepare_site(kid: str) -> dict:
    import client_setup as setup_svc
    loaded = load_kunde(kid)
    if not loaded:
        raise ValueError("Kunde nicht gefunden")
    k, path = loaded
    result = setup_svc.prepare_webroot(kid)
    if result.get("ok"):
        _log_history(k, path, "webroot", f"{result.get('webroot')} ({result.get('files_copied', 0)} Dateien)")
    return result

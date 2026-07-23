"""Präzise Intention: Stack, Kosten, Probleme, Umsatz, Offenheit, Angebot."""
from __future__ import annotations

from budget import assess_budget
from openness import assess_openness
from problems import detect_problems, problems_summary, solutions_summary
from providers import counter_pitch, detect_providers, estimate_monthly_spend, stack_summary
from revenue import estimate_revenue
from addons import format_call_script, resolve_addon, resolve_call_script
from roi import estimate_roi


def _who_to_contact(lead: dict, sig: dict) -> str:
    person = (sig.get("contact_person") or "").strip()
    if person:
        return person
    if sig.get("legal_form"):
        return f"Inhaber/GF ({sig['legal_form']})"
    return "Inhaber / Geschäftsführung"


def _best_contact(lead: dict, sig: dict) -> dict:
    email = lead.get("email") or ""
    if sig.get("contact_emails"):
        email = email or sig["contact_emails"][0]
    elif sig.get("email_found"):
        email = email or sig["email_found"][0]
    phone = lead.get("phone") or ""
    if sig.get("contact_phones"):
        phone = phone or sig["contact_phones"][0]
    return {
        "name": sig.get("contact_person") or "",
        "email": email,
        "phone": phone,
        "who": _who_to_contact(lead, sig),
    }


def _match_when(when: str, lead: dict, sig: dict, vertical: dict) -> bool:
    gp = lead.get("google_places") or {}
    prio = vertical.get("priority_amenities") or []
    providers = sig.get("providers") or []

    if when == "delivery_platforms":
        return bool(sig.get("delivery_platforms")) or any(p.get("category") == "delivery" for p in providers)
    if when == "no_website_or_social":
        return not sig.get("has_website") or sig.get("only_social_site")
    if when == "job_signals":
        return bool(sig.get("job_signals"))
    if when == "no_order_signals":
        return (
            sig.get("checked")
            and not sig.get("order_signals")
            and (not prio or lead.get("amenity") in prio or lead.get("amenity"))
        )
    if when == "trust_issue":
        return (gp.get("rating") and float(gp["rating"]) < 4.0) or (
            sig.get("has_website") and not sig.get("https")
        )
    if when == "has_paid_tools":
        return any((p.get("monthly_min") or 0) > 0 for p in providers)
    if when == "default":
        return True
    return False


def _actions_for(vertical: dict, code: str, budget: dict, sig: dict, providers: list[dict]) -> list[str]:
    offer = (vertical.get("offers") or {}).get(budget.get("offer_key", "standard"), {})
    includes = list(offer.get("includes") or [])

    extras: list[str] = []
    vid = vertical.get("vertical") or vertical.get("id", "")

    if code == "provision" and any(p.get("category") == "delivery" for p in providers):
        d = next(p for p in providers if p.get("category") == "delivery")
        extras.append(f"ROI-Rechnung: {d['name']} vs. eigenes Portal (Referenz Snack House)")
    if sig.get("job_signals"):
        extras.append("SMS Bestelllink bei Anruf, entlastet Team ohne neues Personal")
    if not sig.get("mobile_viewport") and sig.get("has_website"):
        extras.append("Mobil-optimiertes Portal, Gäste bestellen am Handy")
    if sig.get("pdf_menu"):
        extras.append("PDF-Speisekarte → digitale Karte mit QR am Tisch")
    if budget.get("tier") == "C":
        extras.extend((vertical.get("local_wins") or [])[:3])

    seen: set[str] = set()
    out: list[str] = []
    for item in includes + extras:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out[:6]


def derive_intent(lead: dict, sig: dict, vertical: dict | None = None) -> dict:
    vertical = vertical or {}
    vid = vertical.get("vertical") or vertical.get("id", "")

    # Provider detection (if not already in sig from crawl)
    if "providers" not in sig:
        text_blob = " ".join(
            filter(None, [
                sig.get("title", ""),
                " ".join(sig.get("delivery_platforms") or []),
                " ".join(sig.get("cms") or []),
                " ".join(sig.get("order_signals") or []),
            ])
        )
        host = (sig.get("final_url") or lead.get("website") or "")
        sig["providers"] = detect_providers(text_blob, host, sig)
    providers = sig.get("providers") or []

    budget = assess_budget(lead, sig, providers, vertical)
    revenue = estimate_revenue(lead, sig)
    problems = detect_problems(lead, sig, vid)
    openness = assess_openness(lead, sig, revenue, problems)
    buy_signals = budget.get("buy_signals") or []
    roi = estimate_roi(lead, sig, providers, revenue, buy_signals)
    addon = resolve_addon(providers, buy_signals)
    call_script = resolve_call_script(buy_signals)
    call_script_text = format_call_script(call_script)

    # Kontakt-Priorität mit Offenheit + Umsatz verfeinern
    if budget.get("contact_priority") == "call" and openness.get("tier") == "resistent":
        budget["contact_priority"] = "nurture"
        budget["action"] = "Nicht kalt anrufen, Traditionsbetrieb. " + (openness.get("successor_hint") or "")
    elif budget.get("contact_priority") == "skip" and openness.get("tier") == "offen" and revenue.get("can_afford_monthly"):
        budget["contact_priority"] = "nurture"
        budget["action"] = "Per E-Mail/Instagram, offen, aber Budget knapp. Starter-Paket anbieten."

    intents_cfg = vertical.get("intents") or {}
    code = "standard"
    order = ["provision", "digital_neu", "entlastung", "umsatz", "leads", "vertrauen", "has_paid_tools", "standard"]

    for key in order:
        spec = intents_cfg.get(key)
        if not spec:
            continue
        when = spec.get("when", "default")
        if when == "default":
            code = key
            break
        if _match_when(when, lead, sig, vertical):
            code = key
            break

    spec = intents_cfg.get(code, intents_cfg.get("standard", {}))
    contact = _best_contact(lead, sig)
    actions = _actions_for(vertical, code, budget, sig, providers)
    spend = estimate_monthly_spend(providers)
    counter = counter_pitch(providers, vid)

    # Präzise want/approach
    want = spec.get("want", "")
    if providers:
        want = f"{want} · Aktuell: {stack_summary(providers)[:120]}"

    approach_parts = []
    if counter:
        approach_parts.append(counter)
    if budget.get("offer_name"):
        approach_parts.append(
            f"Angebot: {budget['offer_name']} ({budget.get('offer_setup', '?')} + {budget.get('offer_monthly', '?')})"
        )
    if actions:
        approach_parts.append("Jetzt: " + "; ".join(actions[:3]))
    if problems:
        approach_parts.append("Probleme: " + problems_summary(problems))
    if revenue.get("label"):
        approach_parts.append(f"Umsatz-Schätzung: {revenue['label']} ({revenue.get('digital_uplift_est', '')})")
    if openness.get("reason_summary"):
        approach_parts.append(f"Offenheit: {openness['label']}, {openness['reason_summary']}")
    approach = " ".join(approach_parts) or spec.get("approach", "")

    automations = []
    for p in problems[:4]:
        if p.get("automation"):
            automations.append(p["automation"])

    return {
        "code": code,
        "label": spec.get("label", "Akquise"),
        "want": want,
        "approach": approach,
        "who": contact["who"],
        "contact_name": contact["name"],
        "contact_email": contact["email"],
        "contact_phone": contact["phone"],
        "stack": providers,
        "stack_summary": stack_summary(providers),
        "monthly_spend_est": spend,
        "counter_pitch": counter,
        "action_now": actions,
        "offer_tier": budget.get("offer_key", ""),
        "offer_name": budget.get("offer_name", ""),
        "offer_setup": budget.get("offer_setup", ""),
        "offer_monthly": budget.get("offer_monthly", ""),
        "budget_tier": budget.get("tier", "?"),
        "budget_label": budget.get("label", ""),
        "budget_score": budget.get("score", 0),
        "contact_priority": budget.get("contact_priority", "nurture"),
        "contact_action": budget.get("action", ""),
        "budget_reason": budget.get("reason_summary", ""),
        "buy_ready": bool(budget.get("buy_ready")),
        "buy_signals": budget.get("buy_signals") or [],
        "buy_summary": budget.get("buy_summary") or "",
        "addon_pitch": budget.get("addon_pitch") or addon.get("addon") or "",
        "addon_keep": addon.get("keep") or "",
        "addon_value": addon.get("value") or "",
        "roi": roi,
        "roi_label": roi.get("label") or "",
        "roi_uplift_eur": roi.get("addon_uplift_eur"),
        "roi_payback_months": roi.get("payback_months"),
        "call_script": call_script,
        "call_script_text": call_script_text,
        "problems": problems,
        "problems_summary": problems_summary(problems),
        "solutions_summary": solutions_summary(problems),
        "automations": automations,
        "revenue": revenue,
        "revenue_label": revenue.get("label", ""),
        "revenue_uplift": revenue.get("digital_uplift_est", ""),
        "openness": openness,
        "openness_tier": openness.get("tier", ""),
        "openness_label": openness.get("label", ""),
        "openness_score": openness.get("score", 0),
        "successor_hint": openness.get("successor_hint", ""),
        "local_rank": lead.get("local_rank") or {},
        "local_rank_label": (lead.get("local_rank") or {}).get("label", ""),
        "local_rank_pitch": (lead.get("local_rank") or {}).get("pitch", ""),
        "triggers": lead.get("triggers") or [],
    }

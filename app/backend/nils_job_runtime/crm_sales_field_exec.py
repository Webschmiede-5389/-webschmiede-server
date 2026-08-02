# -*- coding: utf-8 -*-
"""Execute Second-Manager sales field capabilities (inline + Freigabe)."""
from __future__ import annotations

import logging
import re
from typing import Any

from nils_job_runtime import crm_language
from nils_job_runtime import crm_offer_exec as offer_exec
from nils_job_runtime import crm_sales_field_service as crm
from nils_job_runtime import store
from nils_job_runtime import turn_context as tc

log = logging.getLogger("nils_job_runtime.crm_sales_field_exec")

WRITE_CAPS = frozenset(
    {
        "crm.note_create",
        "crm.deal_stage_update",
        "crm.deal_open",
        "crm.offer_write",
        "crm.deal_close",
    }
)

CAP_TO_INTENT = {
    "crm.pipeline_read": tc.INTENT_CRM_PIPELINE_READ,
    "crm.lead_thread": tc.INTENT_CRM_LEAD_THREAD,
    "crm.note_create": tc.INTENT_CRM_NOTE_CREATE,
    "crm.deal_stage_update": tc.INTENT_CRM_DEAL_STAGE,
    "crm.deal_open": tc.INTENT_CRM_DEAL_OPEN,
    "crm.offer_write": tc.INTENT_CRM_OFFER_WRITE,
    "crm.deal_close": tc.INTENT_CRM_DEAL_CLOSE,
}


def intent_for_capability(cap: str) -> str:
    return CAP_TO_INTENT.get(cap, tc.INTENT_CRM_PIPELINE_READ)


def _resolve_company(turn: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """Returns (turn, error_reply). Mutates collected company_id."""
    collected = dict(turn.get("collected_parameters") or {})
    if collected.get("company_id"):
        turn["collected_parameters"] = collected
        return turn, None
    q = (collected.get("company") or collected.get("customer") or "").strip()
    if not q:
        turn["missing_parameters"] = ["company"]
        turn["state"] = tc.STATE_WAITING_FOR_INPUT
        return turn, crm_language.ask_company_prompt()
    hits = crm.search_companies(q)
    if not hits:
        return turn, crm_language.company_not_found(q)
    if len(hits) > 1:
        exact = [h for h in hits if h.name.lower() == q.lower()]
        if len(exact) != 1:
            turn["candidates"] = {
                "companies": [
                    {"id": h.id, "name": h.name, "customer_number": h.customer_number}
                    for h in hits
                ]
            }
            turn["missing_parameters"] = ["customer_choice"]
            turn["state"] = tc.STATE_AWAITING_CUSTOMER_CHOICE
            return turn, crm.format_company_choices(hits)
        hits = exact
    collected["company_id"] = hits[0].id
    collected["company"] = hits[0].name
    collected["customer"] = hits[0].name
    turn["collected_parameters"] = collected
    turn["missing_parameters"] = []
    return turn, None


def _park_approval(jid: str, turn: dict[str, Any], prompt: str, capability: str) -> dict[str, Any]:
    turn["missing_parameters"] = []
    turn["state"] = tc.STATE_AWAITING_SALES_APPROVAL
    tc.save(jid, turn)
    extra = {
        "pipeline_stage": "APPROVAL_CHECK",
        "approval_required": capability,
        "progress_message": f"Warte auf Freigabe: {capability}",
        "capability": capability,
    }
    try:
        job = store.get_job(jid)
        assert job
        cur = job["status"]
        if cur == "RECEIVED":
            job = store.transition(
                jid, "PREFLIGHT", extra={"pipeline_stage": "APPROVAL_CHECK"}
            )
            cur = job["status"]
        if cur in ("PREFLIGHT", "NEEDS_CLARIFICATION"):
            store.transition(jid, "WAITING_FOR_APPROVAL", extra=extra)
        elif cur != "WAITING_FOR_APPROVAL":
            store.update_fields(
                jid,
                progress_message=prompt[:200],
                capability=capability,
                approval_required=capability,
            )
        else:
            store.update_fields(
                jid,
                progress_message=prompt[:200],
                capability=capability,
                approval_required=capability,
            )
    except Exception:
        log.exception("sales_park_approval")
    return store.get_job(jid) or {}


def _strip_termin_clause(text: str) -> str:
    return re.sub(
        r"(?i)\s*\btermin\b(?:\s*[:=])?\s*.+$",
        "",
        text or "",
        flags=re.M,
    ).strip()


def _want_termin(text: str, collected: dict[str, Any]) -> bool:
    if str(collected.get("want_termin") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return True
    return bool(re.search(r"(?i)\btermin\b", text or ""))


def _extract_next_step(text: str, collected: dict[str, Any]) -> str:
    if collected.get("next_action") or collected.get("next_step"):
        return str(
            collected.get("next_action") or collected.get("next_step") or ""
        ).strip()
    m = re.search(
        r"(?i)(?:nächster\s+schritt|naechster\s+schritt|next\s*step|follow[- ]?up)\s*[:=]\s*"
        r"(.+?)(?=\s*\btermin\b|$)",
        text or "",
        re.M | re.S,
    )
    if m:
        return m.group(1).strip()[:255]
    return ""


def _extract_note(text: str, collected: dict[str, Any]) -> str:
    if collected.get("note"):
        return str(collected["note"]).strip()
    # Strip next-step + termin so they don't pollute the note body
    raw = text or ""
    raw_wo = re.sub(
        r"(?i)\s*(?:nächster\s+schritt|naechster\s+schritt|next\s*step|follow[- ]?up)\s*[:=]\s*.+$",
        "",
        raw,
        flags=re.M,
    )
    raw_wo = _strip_termin_clause(raw_wo)
    m = re.search(
        r"(?i)(?:notiz|note|vermerk)\s*[:=]\s*(.+)$", raw_wo, re.S
    )
    if m:
        return m.group(1).strip()
    m = re.search(
        r"(?i)(?:notiz|notiere|vermerke|feld[- ]?close|nach\s+dem\s+gespräch|nach\s+dem\s+gespraech)\s+"
        r"(?:bei\s+.+?\s*[:=]\s*|\s*)(.+)$",
        raw_wo,
        re.S,
    )
    if m:
        body = m.group(1).strip()
        # drop "bei Firma X:" / bare "bei ProOffice …" (company, not note)
        body = re.sub(r"(?i)^bei\s+(?:firma\s*[:=]\s*)?.+?\s*[:=]\s*", "", body).strip()
        body = re.sub(r"(?i)^bei\s+(?:firma\s*[:=]\s*)?.+$", "", body).strip()
        if not body:
            return ""
        return body
    return ""


def _create_followup_termin(
    *,
    text: str,
    collected: dict[str, Any],
    company_name: str,
) -> dict[str, Any]:
    """Optional Kalender-Create nach Feld-Close (Zug H)."""
    from nils_job_runtime import calendar_connector as cal
    from nils_job_runtime import calendar_exec as cal_exec

    c = dict(collected)
    # Titel: explizit oder Follow-up — Firma
    title = str(c.get("termin_titel") or c.get("titel") or "").strip()
    if not title:
        m = re.search(
            r"(?i)\btermin\b(?:\s+(?:anlegen|erstellen))?\s*"
            r"(?:titel|betreff)?\s*[:=]?\s*(.+?)(?=\s+(?:heute|morgen|\d)|\s*$)",
            text or "",
        )
        if m:
            cand = m.group(1).strip()
            if cand and not re.search(r"(?i)^(heute|morgen)$", cand):
                title = cand[:120]
    if not title:
        title = f"Follow-up — {company_name or 'Lead'}"
    c["titel"] = title
    draft = cal_exec._parse_draft(text or "", c)
    draft.title = title
    draft.description = f"Street-Close via Nils · {company_name or ''}".strip()
    conn = cal.CalendarConnector()
    result = conn.create(draft, approved=True, invite=False)
    event = result.get("event") or {}
    return {
        "ok": bool(result.get("ok")),
        "event": event if isinstance(event, dict) else {},
        "calendar_id": str(
            (event or {}).get("calendar_id")
            or conn.cfg.allowed_calendar_id
            or conn.cfg.target_name
            or ""
        ),
        "draft_title": draft.title,
        "draft_start": f"{draft.date} {draft.start_time}",
    }


def _extract_stage(text: str, collected: dict[str, Any]) -> str:
    if collected.get("stage"):
        return str(collected["stage"]).strip()
    t = text or ""

    def _clean(raw: str) -> str:
        s = (raw or "").strip().strip(" \"'")
        s = re.split(r"(?i)\s+bei\b", s, maxsplit=1)[0].strip()
        s = re.sub(r"(?i)^(die|der|das|stage|phase|pipeline)\s+", "", s).strip()
        return s[:80]

    patterns = (
        # Deal auf Angebot bei Firma
        r"(?i)\bdeal\s+(?:auf|nach)\s+[\"']?([^\"'\n]+?)[\"']?(?:\s+bei\b|$)",
        # Stage: Angebot bei … / Stage Angebot bei …
        r"(?i)\b(?:stage|phase)\s*[:=]\s*[\"']?([^\"'\n]+?)[\"']?(?:\s+bei\b|$)",
        r"(?i)\b(?:stage|phase)\s+[\"']?([^\"'\n]+?)[\"']?\s+bei\b",
        # … auf die Stage Angebot
        r"(?i)(?:auf|nach|in)\s+(?:die\s+|der\s+)?(?:stage|phase)\s+[\"']?([^\"'\n]+)[\"']?",
        # Deal verschieben bei Firma auf Angebot
        r"(?i)(?:deal\s+)?verschieb\w*.+?\s+(?:auf|nach)\s+[\"']?([^\"'\n]+?)[\"']?\s*$",
        r"(?i)(?:stage|phase|pipeline)\s*[:=]\s*[\"']?([^\"'\n]+)[\"']?",
    )
    for pat in patterns:
        m = re.search(pat, t)
        if m:
            stage = _clean(m.group(1))
            if stage:
                return stage
    return ""


def _extract_money(text: str) -> tuple[float | None, float | None]:
    setup = monthly = None
    m = re.search(r"(?i)setup\s*[:=]?\s*(\d+(?:[.,]\d+)?)", text or "")
    if m:
        setup = float(m.group(1).replace(",", "."))
    m = re.search(r"(?i)(?:monat|monthly)\s*[:=]?\s*(\d+(?:[.,]\d+)?)", text or "")
    if m:
        monthly = float(m.group(1).replace(",", "."))
    return setup, monthly


def _extract_close_outcome(text: str, collected: dict[str, Any]) -> str:
    if collected.get("outcome"):
        return str(collected["outcome"]).strip().lower()
    t = (text or "").lower()
    if re.search(r"\b(gewonnen|won|close\s*won|won[- ]?ritual)\b", t):
        return "won"
    if re.search(
        r"\b(verloren|lost|close\s*lost|lost[- ]?ritual|verlust)\b", t
    ):
        return "lost"
    return ""


def _extract_lost_reason(text: str, collected: dict[str, Any]) -> str:
    if collected.get("lost_reason") or collected.get("grund"):
        return str(
            collected.get("lost_reason") or collected.get("grund") or ""
        ).strip()[:500]
    m = re.search(
        r"(?i)(?:grund|reason|lost_reason|weil)\s*[:=]\s*(.+?)(?=\s+(?:mit\s+beleg|ohne\s+beleg)\b|$)",
        text or "",
        re.S,
    )
    if m:
        return m.group(1).strip()[:500]
    return ""


def _want_won_beleg(text: str, collected: dict[str, Any]) -> bool:
    """Won-Ritual: Drive-Kurzdoc im Agency-Sales-Root (default an)."""
    flag = str(collected.get("want_beleg") or collected.get("beleg") or "").strip().lower()
    if flag in ("0", "false", "no", "off", "ohne"):
        return False
    if flag in ("1", "true", "yes", "on"):
        return True
    t = text or ""
    if re.search(
        r"(?i)\bohne\s+(?:beleg|doc|dokument|drive|kurzdoc)\b|"
        r"\bkein(?:en?)?\s+(?:beleg|doc|drive)\b",
        t,
    ):
        return False
    return True


def _want_lost_beleg(text: str, collected: dict[str, Any]) -> bool:
    """Lost-Ritual: Drive-Kurzdoc optional (default aus)."""
    flag = str(collected.get("want_beleg") or collected.get("beleg") or "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return True
    if flag in ("0", "false", "no", "off", "ohne"):
        return False
    return bool(re.search(r"(?i)\bmit\s+(?:beleg|doc|drive|kurzdoc)\b", text or ""))


def _create_won_beleg_doc(
    *,
    company_name: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Kurzdoc als Won-Beleg — nur Agency-Sales Root."""
    from nils_job_runtime import drive_connector as drive

    num = str(result.get("customer_number") or "–")
    title = f"Won — {company_name or 'Firma'} — {num}"[:120]
    body = "\n".join(
        [
            "Won-Ritual (Nils)",
            f"Firma: {company_name or '–'}",
            f"Kundennummer: {num}",
            f"Lifecycle: {result.get('lifecycle_status') or '–'}",
            f"Deal: {result.get('deal_title') or '–'} (#{result.get('deal_id') or '–'})",
            f"Stage: {result.get('stage') or '–'}",
            "",
            "Scope: AGENCY — keine Kunden-Portal-Provisionierung.",
        ]
    )
    conn = drive.DriveConnector()
    return conn.create_doc(title=title, body=body, approved=True)


def _create_lost_beleg_doc(
    *,
    company_name: str,
    result: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    from nils_job_runtime import drive_connector as drive

    title = f"Lost — {company_name or 'Firma'}"[:120]
    body = "\n".join(
        [
            "Lost-Ritual (Nils)",
            f"Firma: {company_name or '–'}",
            f"Grund: {reason or '–'}",
            f"Deal: {result.get('deal_title') or '–'} (#{result.get('deal_id') or '–'})",
            f"Stage: {result.get('stage') or '–'}",
            "",
            "Kein CUSTOMER / keine Kundennummer.",
        ]
    )
    conn = drive.DriveConnector()
    return conn.create_doc(title=title, body=body, approved=True)


def execute_sales_field(
    *,
    job: dict[str, Any],
    turn: dict[str, Any],
    capability: str,
    approval_granted: bool = False,
    original_text: str = "",
) -> dict[str, Any]:
    jid = job["job_id"]
    text = original_text or (job.get("original_request") or "")

    if not crm.cap_enabled(capability):
        reply = "Diese Aktion kann ich aktuell noch nicht ausführen."
        turn["state"] = tc.STATE_FAILED
        tc.save(jid, turn)
        return {
            "ok": False,
            "reply": reply,
            "job": offer_exec._fail(jid, reply, category="cap_off"),
            "turn": turn,
            "terminal": True,
        }

    probe = crm.probe()
    if not probe.get("ok"):
        reply = f"CRM nicht erreichbar ({probe.get('detail')})."
        turn["state"] = tc.STATE_FAILED
        tc.save(jid, turn)
        return {
            "ok": False,
            "reply": reply,
            "job": offer_exec._fail(jid, reply, category="crm_unreachable"),
            "turn": turn,
            "terminal": True,
        }

    collected = dict(turn.get("collected_parameters") or {})

    # --- pipeline / briefing / sla / debrief (no company) ---
    if capability == "crm.pipeline_read":
        tlow = (text or "").lower()
        mode = str(collected.get("pipeline_mode") or "").lower()
        if (
            mode == "morning"
            or re.search(
                r"(?i)morgen[- ]?briefing|briefing\s+morgen|lage\s+morgen|"
                r"guten\s+morgen\s+nils|manager[- ]?briefing",
                text or "",
            )
        ):
            reply = crm.morning_briefing_text()
            ref = "pipeline:morning"
        elif mode == "funnel" or re.search(
            r"(?i)funnel[- ]?review|wochen[- ]?review|funnel\s+heute|"
            r"verkaufs[- ]?review|wochen[- ]?funnel",
            text or "",
        ):
            reply = crm.funnel_review_text(days=7)
            ref = "pipeline:funnel"
        elif (
            mode == "sla"
            or re.search(
                r"(?i)follow[- ]?up\s*sla|sla\s+heute|nachfass[- ]?sla|"
                r"heiss(?:e)?\s+leads|heiße\s+leads|warme\s+leads|"
                r"welche\s+leads\s+sind\s+(?:heiss|heiß|warm)",
                text or "",
            )
        ):
            reply = crm.sla_report_text()
            ref = "pipeline:sla"
        elif mode == "debrief" or re.search(
            r"(?i)abend[- ]?debrief|tagesabschluss|abend[- ]?review",
            text or "",
        ):
            # note: bare "debrief" stays coach (telegram_agent); hier nur Abend-Debrief CRM
            reply = crm.evening_debrief_text()
            ref = "pipeline:debrief"
        elif (
            mode == "briefing"
            or re.search(r"(?i)pipeline\s+heute|feld[- ]?briefing|briefing\s+heute|lage\s+heute", text or "")
            or re.search(r"(?i)\bheute\b", tlow)
            and "pipeline" in tlow
        ):
            reply = crm.field_briefing()
            ref = "pipeline:briefing"
        elif mode == "stale" or re.search(
            r"(?i)stille\s+leads|kalte\s+leads|nachfassen|liegen\s+geblieben",
            text or "",
        ):
            reply = crm.stale_leads_text()
            ref = "pipeline:stale"
        else:
            board = crm.pipeline_board()
            reply = crm.format_pipeline(board)
            ref = "pipeline"
        turn["state"] = tc.STATE_DONE
        tc.save(jid, turn)
        return offer_exec._succeed(jid, turn, reply, offer_number=ref)

    want_followup_suggest = bool(
        re.search(
            r"(?i)follow[- ]?up\s*(?:vorschlag|skript|tipp)|nachfass[- ]?vorschlag",
            text or "",
        )
    )

    # company-scoped
    turn, err = _resolve_company(turn)
    if err:
        tc.save(jid, turn)
        if turn.get("state") == tc.STATE_AWAITING_CUSTOMER_CHOICE or turn.get(
            "missing_parameters"
        ):
            return {
                "ok": False,
                "reply": err,
                "job": offer_exec._clarify(jid, err, turn),
                "turn": turn,
                "terminal": False,
            }
        turn["state"] = tc.STATE_FAILED
        tc.save(jid, turn)
        return {
            "ok": False,
            "reply": err,
            "job": offer_exec._fail(jid, err, category="customer_not_found"),
            "turn": turn,
            "terminal": True,
        }

    collected = dict(turn.get("collected_parameters") or {})
    company_id = int(collected["company_id"])

    if capability == "crm.lead_thread":
        if want_followup_suggest:
            reply = crm.followup_suggestion_text(company_id)
            turn["state"] = tc.STATE_DONE
            tc.save(jid, turn)
            return offer_exec._succeed(
                jid, turn, reply, offer_number="followup:suggest"
            )
        thread = crm.lead_thread(company_id)
        if not thread:
            reply = "Firma nicht gefunden."
            turn["state"] = tc.STATE_FAILED
            tc.save(jid, turn)
            return {
                "ok": False,
                "reply": reply,
                "job": offer_exec._fail(jid, reply, category="customer_not_found"),
                "turn": turn,
                "terminal": True,
            }
        reply = crm.format_thread(thread)
        turn["state"] = tc.STATE_DONE
        tc.save(jid, turn)
        return offer_exec._succeed(
            jid, turn, reply, offer_number=f"thread:{company_id}"
        )

    # writes need approval
    if capability in WRITE_CAPS and not approval_granted:
        if capability == "crm.note_create":
            note = _extract_note(text, collected)
            next_a = _extract_next_step(text, collected)
            if not note:
                turn["missing_parameters"] = ["note"]
                turn["state"] = tc.STATE_WAITING_FOR_INPUT
                prompt = (
                    "Street-Close: Notiz + optional nächster Schritt + optional Termin.\n"
                    "Beispiel:\n"
                    "notiz: war vor Ort, Interesse hoch\n"
                    "nächster Schritt: Angebot schicken\n"
                    "Termin morgen 10:00"
                )
                tc.save(jid, turn)
                return {
                    "ok": False,
                    "reply": prompt,
                    "job": offer_exec._clarify(jid, prompt, turn),
                    "turn": turn,
                    "terminal": False,
                }
            collected["note"] = note
            if next_a:
                collected["next_action"] = next_a
            want_cal = _want_termin(text, collected)
            collected["want_termin"] = "1" if want_cal else "0"
            termin_line = ""
            if want_cal:
                from nils_job_runtime import calendar_exec as cal_exec

                title = f"Follow-up — {collected.get('company') or 'Lead'}"
                cprev = dict(collected)
                cprev["titel"] = title
                draft = cal_exec._parse_draft(text, cprev)
                collected["termin_titel"] = title
                collected["termin_datum"] = draft.date
                collected["termin_zeit"] = draft.start_time
                termin_line = f"Termin: {draft.date} {draft.start_time} — {title}\n"
            turn["collected_parameters"] = collected
            prompt = (
                f"Freigabe nötig — Street-Close:\n"
                f"Firma: {collected.get('company')}\n"
                f"Notiz: {note[:400]}\n"
                f"Nächster Schritt: {next_a or '–'}\n"
                f"{termin_line}"
                'Antworte mit „ja“, sonst „stop“.'
            )
        elif capability == "crm.deal_stage_update":
            stage = _extract_stage(text, collected)
            if not stage:
                turn["missing_parameters"] = ["stage"]
                turn["state"] = tc.STATE_WAITING_FOR_INPUT
                prompt = "Auf welche Pipeline-Stage? (stage: Name)"
                tc.save(jid, turn)
                return {
                    "ok": False,
                    "reply": prompt,
                    "job": offer_exec._clarify(jid, prompt, turn),
                    "turn": turn,
                    "terminal": False,
                }
            collected["stage"] = stage
            turn["collected_parameters"] = collected
            prompt = (
                f"Freigabe nötig — Deal verschieben:\n"
                f"Firma: {collected.get('company')}\n"
                f"Stage: {stage}\n"
                'Antworte mit „ja“, sonst „stop“.'
            )
        elif capability == "crm.deal_open":
            turn["collected_parameters"] = collected
            prompt = (
                "Freigabe nötig — Neuer / offener Deal:\n"
                f"Firma: {collected.get('company')}\n"
                "Wirkung: offenen Deal bestätigen oder neu anlegen "
                "(wenn keiner offen / nach Lost)\n"
                'Antworte mit „ja“, sonst „stop“.'
            )
        elif capability == "crm.offer_write":
            variant = crm.resolve_offer_variant(text)
            if variant:
                collected["variant"] = variant.get("label") or variant.get("key")
                collected["title"] = collected.get("title") or variant.get("title") or ""
                collected["services"] = variant.get("services") or ""
                if collected.get("setup_eur") is None:
                    collected["setup_eur"] = variant.get("setup_eur")
                if collected.get("monthly_eur") is None:
                    collected["monthly_eur"] = variant.get("monthly_eur")
            setup, monthly = _extract_money(text)
            if setup is not None:
                collected["setup_eur"] = setup
            if monthly is not None:
                collected["monthly_eur"] = monthly
            turn["collected_parameters"] = collected
            var_line = (
                f"Variante: {collected.get('variant')}\n"
                if collected.get("variant")
                else ""
            )
            prompt = (
                f"Freigabe nötig — Angebot (Entwurf) anlegen:\n"
                f"Firma: {collected.get('company')}\n"
                f"{var_line}"
                f"Titel: {collected.get('title') or '–'}\n"
                f"Setup: {collected.get('setup_eur', '–')} | Monat: {collected.get('monthly_eur', '–')}\n"
                'Antworte mit „ja“, sonst „stop“.'
            )
        else:  # deal_close
            outcome = _extract_close_outcome(text, collected)
            if not outcome:
                turn["missing_parameters"] = ["outcome"]
                turn["state"] = tc.STATE_WAITING_FOR_INPUT
                prompt = "Gewonnen oder verloren? (gewonnen / verloren)"
                tc.save(jid, turn)
                return {
                    "ok": False,
                    "reply": prompt,
                    "job": offer_exec._clarify(jid, prompt, turn),
                    "turn": turn,
                    "terminal": False,
                }
            collected["outcome"] = outcome
            if outcome == "won":
                want_beleg = _want_won_beleg(text, collected)
                collected["want_beleg"] = "1" if want_beleg else "0"
                turn["collected_parameters"] = collected
                beleg_line = (
                    "\nBeleg: Kurzdoc in Agency-Sales"
                    if want_beleg
                    else "\nBeleg: ohne Drive-Doc"
                )
                prompt = (
                    "Freigabe nötig — Won-Ritual:\n"
                    f"Firma: {collected.get('company')}\n"
                    "Wirkung: Deal → Won, Lifecycle CUSTOMER + Kundennummer"
                    f"{beleg_line}\n"
                    "(kein Kunden-Portal-Deploy)\n"
                    'Antworte mit „ja“, sonst „stop“.'
                )
            else:
                reason = _extract_lost_reason(text, collected)
                if not reason:
                    turn["missing_parameters"] = ["lost_reason"]
                    turn["state"] = tc.STATE_WAITING_FOR_INPUT
                    turn["collected_parameters"] = collected
                    prompt = (
                        "Lost-Ritual — warum verloren?\n"
                        "Beispiel: grund: zu teuer / keine Zeit / Konkurrenz"
                    )
                    tc.save(jid, turn)
                    return {
                        "ok": False,
                        "reply": prompt,
                        "job": offer_exec._clarify(jid, prompt, turn),
                        "turn": turn,
                        "terminal": False,
                    }
                collected["lost_reason"] = reason
                want_beleg = _want_lost_beleg(text, collected)
                collected["want_beleg"] = "1" if want_beleg else "0"
                turn["collected_parameters"] = collected
                beleg_line = (
                    "\nBeleg: Kurzdoc in Agency-Sales"
                    if want_beleg
                    else "\nBeleg: ohne Drive-Doc"
                )
                prompt = (
                    "Freigabe nötig — Lost-Ritual:\n"
                    f"Firma: {collected.get('company')}\n"
                    f"Grund: {reason}\n"
                    "Wirkung: Deal → Lost (kein CUSTOMER / keine Nummer)"
                    f"{beleg_line}\n"
                    'Antworte mit „ja“, sonst „stop“.'
                )
        job2 = _park_approval(jid, turn, prompt, capability)
        return {
            "ok": False,
            "reply": prompt,
            "job": job2,
            "turn": turn,
            "terminal": False,
        }

    # approved / execute writes
    try:
        if capability == "crm.note_create":
            note = str(collected.get("note") or _extract_note(text, collected)).strip()
            next_a = str(
                collected.get("next_action")
                or _extract_next_step(text, collected)
                or ""
            ).strip()
            result = crm.add_note(
                company_id=company_id, note=note, next_action=next_a
            )
            company_name = str(
                result.get("company_name") or collected.get("company") or ""
            )
            reply = (
                f"Street-Close gespeichert.\nFirma: {company_name}\n"
                f"Notiz: {result.get('note')}"
            )
            if result.get("next_action"):
                reply += f"\nNächster Schritt: {result.get('next_action')}"
            if result.get("deal_id"):
                reply += f"\nDeal #{result.get('deal_id')}"
            # Zug H: optional Termin im selben Freigabe-Zyklus
            if _want_termin(text, collected):
                try:
                    cal_c = dict(collected)
                    if collected.get("termin_titel"):
                        cal_c["titel"] = collected["termin_titel"]
                    if collected.get("termin_datum"):
                        cal_c["datum"] = collected["termin_datum"]
                    cal_res = _create_followup_termin(
                        text=text,
                        collected=cal_c,
                        company_name=company_name,
                    )
                    if cal_res.get("ok"):
                        from nils_job_runtime import calendar_exec as cal_exec

                        meeting = cal_exec.format_meeting_set(
                            cal_res.get("event") or {},
                            calendar_id=cal_res.get("calendar_id") or "",
                        )
                        reply += "\n\n" + meeting
                    else:
                        reply += (
                            "\n\nTermin: nicht angelegt "
                            f"({cal_res.get('draft_start') or '–'})"
                        )
                except Exception as e:
                    log.exception("street_close_termin")
                    reply += f"\n\nTermin fehlgeschlagen: {type(e).__name__}: {e}"
        elif capability == "crm.deal_stage_update":
            stage = str(collected.get("stage") or _extract_stage(text, collected))
            result = crm.update_stage(company_id=company_id, stage_query=stage)
            reply = (
                f"Deal verschoben.\n{result.get('deal_title')}\n"
                f"{result.get('from_stage')} → {result.get('to_stage')}"
            )
        elif capability == "crm.deal_open":
            result = crm.ensure_open_deal(company_id=company_id)
            if result.get("created"):
                reply = (
                    "Neuer Deal angelegt.\n"
                    f"Firma: {collected.get('company')}\n"
                    f"{result.get('deal_title')} [{result.get('stage')}] "
                    f"#{result.get('deal_id')}"
                )
            else:
                reply = (
                    "Offener Deal bereits vorhanden.\n"
                    f"Firma: {collected.get('company')}\n"
                    f"{result.get('deal_title')} [{result.get('stage')}] "
                    f"#{result.get('deal_id')}"
                )
        elif capability == "crm.offer_write":
            if not collected.get("variant"):
                variant = crm.resolve_offer_variant(text)
                if variant:
                    collected["variant"] = variant.get("label") or variant.get("key")
                    collected["title"] = collected.get("title") or variant.get("title") or ""
                    collected["services"] = collected.get("services") or variant.get("services") or ""
                    if collected.get("setup_eur") is None:
                        collected["setup_eur"] = variant.get("setup_eur")
                    if collected.get("monthly_eur") is None:
                        collected["monthly_eur"] = variant.get("monthly_eur")
            setup = collected.get("setup_eur")
            monthly = collected.get("monthly_eur")
            if setup is None or monthly is None:
                s2, m2 = _extract_money(text)
                setup = setup if setup is not None else s2
                monthly = monthly if monthly is not None else m2
            result = crm.create_offer(
                company_id=company_id,
                title=str(collected.get("title") or ""),
                setup_eur=float(setup) if setup is not None else None,
                monthly_eur=float(monthly) if monthly is not None else None,
                services=str(collected.get("services") or ""),
            )
            reply = (
                f"Angebot angelegt (Entwurf).\n"
                f"{result.get('offer_number')} v{result.get('version')}\n"
                f"Deal #{result.get('deal_id')}"
            )
            if collected.get("variant"):
                reply += f"\nVariante: {collected.get('variant')}"
        elif capability == "crm.deal_close":
            outcome = str(
                collected.get("outcome") or _extract_close_outcome(text, collected)
            )
            lost_reason = str(
                collected.get("lost_reason")
                or _extract_lost_reason(text, collected)
                or ""
            )
            result = crm.close_deal(
                company_id=company_id,
                outcome=outcome,
                lost_reason=lost_reason,
            )
            company_name = str(collected.get("company") or "")
            if str(result.get("outcome") or "") == "won":
                reply = (
                    "Won-Ritual abgeschlossen.\n"
                    f"Firma: {company_name}\n"
                    f"Deal: {result.get('deal_title')} → {result.get('stage')}\n"
                    f"Kunde: {result.get('lifecycle_status') or 'CUSTOMER'} "
                    f"{result.get('customer_number') or '–'}"
                )
                if _want_won_beleg(text, collected):
                    try:
                        from nils_job_runtime import drive_connector as drive

                        doc = _create_won_beleg_doc(
                            company_name=company_name, result=result
                        )
                        reply += "\n\n" + drive.format_created(doc, kind="Won-Beleg")
                    except Exception as e:
                        log.exception("won_ritual_beleg")
                        reply += (
                            f"\n\nDrive-Beleg fehlgeschlagen: "
                            f"{type(e).__name__}: {e}"
                        )
            else:
                reason = lost_reason or str(result.get("lost_reason") or "–")
                reply = (
                    "Lost-Ritual abgeschlossen.\n"
                    f"Firma: {company_name}\n"
                    f"Deal: {result.get('deal_title')} → {result.get('stage')}\n"
                    f"Grund: {reason}\n"
                    "Kein Kunde / keine Kundennummer."
                )
                # CRM-Notiz mit Grund (Street-Log)
                try:
                    crm.add_note(
                        company_id=company_id,
                        note=f"Lost-Ritual: {reason}",
                        next_action="",
                    )
                except Exception:
                    log.exception("lost_ritual_note")
                if _want_lost_beleg(text, collected):
                    try:
                        from nils_job_runtime import drive_connector as drive

                        doc = _create_lost_beleg_doc(
                            company_name=company_name,
                            result=result,
                            reason=reason,
                        )
                        reply += "\n\n" + drive.format_created(doc, kind="Lost-Beleg")
                    except Exception as e:
                        log.exception("lost_ritual_beleg")
                        reply += (
                            f"\n\nDrive-Beleg fehlgeschlagen: "
                            f"{type(e).__name__}: {e}"
                        )
        else:
            reply = "Unbekannte Sales-Capability."
            turn["state"] = tc.STATE_FAILED
            tc.save(jid, turn)
            return {
                "ok": False,
                "reply": reply,
                "job": offer_exec._fail(jid, reply, category="unknown_cap"),
                "turn": turn,
                "terminal": True,
            }
    except Exception as e:
        log.exception("sales_field_exec %s", capability)
        reply = f"Aktion fehlgeschlagen: {type(e).__name__}: {e}"
        turn["state"] = tc.STATE_FAILED
        tc.save(jid, turn)
        return {
            "ok": False,
            "reply": reply,
            "job": offer_exec._fail(jid, reply, category="exec_error"),
            "turn": turn,
            "terminal": True,
        }

    turn["state"] = tc.STATE_DONE
    tc.save(jid, turn)
    return offer_exec._succeed(
        jid, turn, reply, offer_number=f"sales:{capability}:{company_id}"
    )


def apply_missing_field(turn: dict[str, Any], text: str) -> tuple[dict[str, Any], str | None]:
    missing = list(turn.get("missing_parameters") or [])
    if not missing:
        return turn, None
    field = missing[0]
    collected = dict(turn.get("collected_parameters") or {})
    t = (text or "").strip()
    if field == "note":
        collected["note"] = t
    elif field == "stage":
        collected["stage"] = t
    elif field == "outcome":
        collected["outcome"] = t
    elif field == "lost_reason":
        reason = _extract_lost_reason(t, {}) or t
        collected["lost_reason"] = reason
        collected["grund"] = reason
        if not collected.get("outcome"):
            collected["outcome"] = "lost"
    else:
        return turn, None
    turn["collected_parameters"] = collected
    turn["missing_parameters"] = []
    turn["state"] = tc.STATE_READY_TO_EXECUTE
    return turn, None

# -*- coding: utf-8 -*-
"""Execute CRM agency e-mail after approval (inline)."""
from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path
from typing import Any

from nils_job_runtime import crm_email_service as mail
from nils_job_runtime import crm_offer_exec as offer_exec
from nils_job_runtime import crm_offer_service as offer_svc
from nils_job_runtime import offer_pdf
from nils_job_runtime import store
from nils_job_runtime import turn_context as tc

log = logging.getLogger("nils_job_runtime.crm_email_exec")


def _park_approval(jid: str, turn: dict[str, Any], prompt: str) -> dict[str, Any]:
    turn["missing_parameters"] = []
    turn["state"] = tc.STATE_AWAITING_EMAIL_APPROVAL
    tc.save(jid, turn)
    job = store.get_job(jid)
    assert job
    try:
        cur = job["status"]
        if cur == "RECEIVED":
            job = store.transition(
                jid, "PREFLIGHT", extra={"pipeline_stage": "APPROVAL_CHECK"}
            )
            cur = job["status"]
        if cur in ("PREFLIGHT", "NEEDS_CLARIFICATION"):
            job = store.transition(
                jid,
                "WAITING_FOR_APPROVAL",
                extra={
                    "pipeline_stage": "APPROVAL_CHECK",
                    "approval_required": "E-Mail senden",
                    "progress_message": "Warte auf Freigabe: E-Mail",
                    "capability": "crm.email_send",
                },
            )
        elif cur != "WAITING_FOR_APPROVAL":
            job = store.update_fields(
                jid,
                progress_message="Warte auf Freigabe: E-Mail",
                capability="crm.email_send",
                approval_required="E-Mail senden",
            )
    except Exception:
        log.exception("email_park_approval")
        job = store.update_fields(jid, progress_message=prompt[:200], capability="crm.email_send")
    return store.get_job(jid) or job


def _want_offer_pdf(collected: dict[str, Any], job: dict[str, Any]) -> bool:
    flag = str(collected.get("attach_offer_pdf") or "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return True
    text = job.get("original_request") or ""
    return bool(
        re.search(
            r"(?i)angebot\s+pdf\s+an|angebot\w*\s+pdf|"
            r"(?:schick|sende)\w*\s+angebot\w*.*\san\s+[\w.+-]+@",
            text,
        )
    )


def _resolve_offer_for_mail(
    collected: dict[str, Any],
) -> tuple[Any | None, str | None]:
    """Return (offer, error_reply)."""
    onum = str(collected.get("offer_number") or "").strip()
    company = str(collected.get("company") or collected.get("customer") or "").strip()
    company_id = collected.get("company_id")
    if company_id is None and company:
        hits = offer_svc.search_companies(company)
        if not hits:
            return None, f"Kein Unternehmen zu „{company}“ im CRM gefunden."
        if len(hits) > 1:
            exact = [h for h in hits if h.name.lower() == company.lower()]
            hits = exact or hits
        if len(hits) > 1:
            return None, offer_svc.format_company_choices(hits)
        company_id = hits[0].id
        collected["company_id"] = company_id
        collected["company"] = hits[0].name
    if onum:
        offer = offer_svc.get_offer_by_number(
            int(company_id) if company_id is not None else None, onum
        )
        if not offer and company_id is None:
            multi = offer_svc.list_offers_by_number(onum)
            if len(multi) == 1:
                offer = multi[0]
            elif len(multi) > 1:
                return None, offer_svc.format_offer_choices(multi)
        if not offer:
            return None, f"Kein Angebot {onum} im CRM gefunden."
        return offer, None
    if company_id is not None:
        offers = offer_svc.list_offers(int(company_id))
        if not offers:
            return None, "Kein Angebot zu dieser Firma — zuerst Entwurf anlegen."
        if len(offers) > 1:
            # neuestes zuerst, wenn Liste sortiert; sonst Auswahl
            return offers[0], None
        return offers[0], None
    return None, "Für PDF-Mail brauche ich Firma oder Angebotsnummer (ANG-…)."


def _render_offer_bytes(offer: Any) -> tuple[str, bytes]:
    fname = offer_pdf.safe_filename(
        offer_number=str(getattr(offer, "offer_number", "") or "ANG"),
        company_name=str(getattr(offer, "company_name", "") or "Unternehmen"),
    )
    with tempfile.TemporaryDirectory(prefix="nils-offer-mail-") as tmp:
        dest = Path(tmp) / fname
        offer_pdf.render_offer_pdf(offer, dest=dest)
        return fname, dest.read_bytes()


def execute_email_send(
    *,
    job: dict[str, Any],
    turn: dict[str, Any],
    approval_granted: bool = False,
) -> dict[str, Any]:
    jid = job["job_id"]
    collected = dict(turn.get("collected_parameters") or {})
    try:
        if not mail.cap_enabled():
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

        to_addr = mail.normalize_email(
            collected.get("to") or collected.get("empfaenger") or ""
        )
        if not to_addr:
            m = re.search(
                r"[\w.+-]+@[\w.-]+\.\w+", job.get("original_request") or ""
            )
            if m:
                to_addr = mail.normalize_email(m.group(0))
        subject = (collected.get("subject") or collected.get("betreff") or "").strip()
        body = (collected.get("body") or collected.get("inhalt") or "").strip()
        company = (collected.get("company") or collected.get("customer") or "").strip()
        want_pdf = _want_offer_pdf(collected, job)

        attachment_name = ""
        offer = None
        if want_pdf:
            collected["attach_offer_pdf"] = "1"
            offer, err = _resolve_offer_for_mail(collected)
            if err:
                turn["collected_parameters"] = collected
                turn["state"] = tc.STATE_FAILED
                tc.save(jid, turn)
                return {
                    "ok": False,
                    "reply": err,
                    "job": offer_exec._fail(jid, err, category="offer_pdf_mail"),
                    "turn": turn,
                    "terminal": True,
                }
            assert offer is not None
            collected["offer_number"] = str(getattr(offer, "offer_number", "") or "")
            company = str(getattr(offer, "company_name", "") or company)
            collected["company"] = company
            if not subject:
                subject = (
                    f"Angebot {collected['offer_number']} — {company or 'Digitale Handwerkskunst'}"
                )
            if not body:
                body = (
                    f"Guten Tag,\n\n"
                    f"anbei unser Angebot {collected['offer_number']}"
                    f"{' für ' + company if company else ''}.\n\n"
                    f"Bei Fragen melden Sie sich gerne.\n\n"
                    f"Freundliche Grüße\nDigitale Handwerkskunst"
                )
            attachment_name = offer_pdf.safe_filename(
                offer_number=collected["offer_number"],
                company_name=company or "Unternehmen",
            )

        missing: list[str] = []
        if not to_addr:
            missing.append("to")
        if not subject:
            missing.append("subject")
        if not body:
            missing.append("body")
        if missing:
            hints = {
                "to": "An welche E-Mail-Adresse?",
                "subject": "Welcher Betreff?",
                "body": "Was soll im Mailtext stehen?",
            }
            prompt = " ".join(hints[m] for m in missing if m in hints)
            turn["missing_parameters"] = missing
            turn["collected_parameters"] = collected
            turn["state"] = tc.STATE_WAITING_FOR_INPUT
            tc.save(jid, turn)
            return {
                "ok": False,
                "reply": prompt,
                "job": offer_exec._clarify(jid, prompt, turn),
                "turn": turn,
                "terminal": False,
            }

        if not mail.recipient_allowed(to_addr):
            reply = (
                f"Empfänger „{to_addr}“ ist nicht auf der Nils-E-Mail-Allowlist. "
                "Kein Versand."
            )
            turn["state"] = tc.STATE_FAILED
            tc.save(jid, turn)
            return {
                "ok": False,
                "reply": reply,
                "job": offer_exec._fail(jid, reply, category="email_allowlist"),
                "turn": turn,
                "terminal": True,
            }

        collected.update(
            {
                "to": to_addr,
                "empfaenger": to_addr,
                "subject": subject,
                "betreff": subject,
                "body": body,
                "inhalt": body,
                "company": company,
            }
        )
        turn["collected_parameters"] = collected

        if not approval_granted:
            prompt = mail.format_approval(
                to_addr=to_addr,
                subject=subject,
                body=body,
                company_name=company,
                offer_number=str(collected.get("offer_number") or ""),
                attachment_name=attachment_name,
            )
            job2 = _park_approval(jid, turn, prompt)
            return {
                "ok": False,
                "reply": prompt,
                "job": job2,
                "turn": turn,
                "terminal": False,
                "awaiting_approval": True,
            }

        attachments: list[tuple[str, bytes]] = []
        if want_pdf:
            if offer is None:
                offer, err = _resolve_offer_for_mail(collected)
                if err or offer is None:
                    raise RuntimeError(err or "Angebot fehlt")
            fname, raw = _render_offer_bytes(offer)
            attachments.append((fname, raw))

        result = mail.send_agency_mail(
            to_addr=to_addr,
            subject=subject,
            body_text=body,
            company_name=company,
            attachments=attachments or None,
        )
        reply = mail.format_sent(result)
        turn["state"] = tc.STATE_DONE
        turn["missing_parameters"] = []
        tc.save(jid, turn)
        out = offer_exec._succeed(
            jid, turn, reply, offer_number=f"email:{to_addr}"
        )
        store.update_fields(
            jid,
            progress_message="E-Mail Dry-Run" if result.get("dry_run") else "E-Mail gesendet",
            capability="crm.email_send",
            external_kind="crm_email_send",
            external_last_step="dry_run" if result.get("dry_run") else "smtp_sent",
            result_reference=f"crm:email:{result.get('message_id')}:{to_addr}",
        )
        out["job"] = store.get_job(jid) or out["job"]
        return out
    except Exception as e:
        log.exception("crm_email_send")
        reply = f"E-Mail fehlgeschlagen: {type(e).__name__}: {e}"
        turn["state"] = tc.STATE_FAILED
        tc.save(jid, turn)
        return {
            "ok": False,
            "reply": reply[:400],
            "job": offer_exec._fail(jid, reply[:200], category="email_error"),
            "turn": turn,
            "terminal": True,
        }


def apply_missing_field(turn: dict[str, Any], text: str) -> tuple[dict[str, Any], str | None]:
    """Fill next missing e-mail parameter from free text."""
    missing = list(turn.get("missing_parameters") or [])
    if not missing:
        return turn, None
    field = missing[0]
    collected = dict(turn.get("collected_parameters") or {})
    t = (text or "").strip()
    if field == "to":
        m = re.search(r"[\w.+-]+@[\w.-]+\.\w+", t)
        if not m:
            return turn, "Bitte eine gültige E-Mail-Adresse nennen."
        collected["to"] = m.group(0)
        collected["empfaenger"] = collected["to"]
    elif field == "subject":
        collected["subject"] = t[:200]
        collected["betreff"] = collected["subject"]
    elif field == "body":
        collected["body"] = t
        collected["inhalt"] = t
    else:
        return turn, None
    missing = missing[1:]
    turn["collected_parameters"] = collected
    turn["missing_parameters"] = missing
    turn["state"] = (
        tc.STATE_WAITING_FOR_INPUT if missing else tc.STATE_READY_TO_EXECUTE
    )
    return turn, None

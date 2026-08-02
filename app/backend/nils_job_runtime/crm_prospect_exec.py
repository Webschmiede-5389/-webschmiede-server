# -*- coding: utf-8 -*-
"""Execute CRM prospect create after explicit approval (inline)."""
from __future__ import annotations

import logging
from typing import Any

from nils_job_runtime import crm_language
from nils_job_runtime import crm_offer_exec as offer_exec
from nils_job_runtime import crm_prospect_service as crm
from nils_job_runtime import store
from nils_job_runtime import turn_context as tc
from nils_job_runtime import turn_routing as tr

log = logging.getLogger("nils_job_runtime.crm_prospect_exec")


def _park_approval(jid: str, turn: dict[str, Any], prompt: str) -> dict[str, Any]:
    turn["missing_parameters"] = []
    turn["state"] = tc.STATE_AWAITING_PROSPECT_APPROVAL
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
        if cur == "PREFLIGHT":
            job = store.transition(
                jid,
                "WAITING_FOR_APPROVAL",
                extra={
                    "pipeline_stage": "APPROVAL_CHECK",
                    "approval_required": "Interessent anlegen",
                    "progress_message": "Warte auf Freigabe: Interessent",
                    "capability": "crm.prospect_create",
                },
            )
        elif cur == "NEEDS_CLARIFICATION":
            # Allowed path in model? If not, update fields and keep clarify→cancel+new.
            try:
                job = store.transition(
                    jid,
                    "WAITING_FOR_APPROVAL",
                    extra={
                        "pipeline_stage": "APPROVAL_CHECK",
                        "approval_required": "Interessent anlegen",
                        "progress_message": "Warte auf Freigabe: Interessent",
                        "capability": "crm.prospect_create",
                    },
                )
            except Exception:
                job = store.update_fields(
                    jid,
                    progress_message=prompt[:200],
                    capability="crm.prospect_create",
                    approval_required="Interessent anlegen",
                )
        elif cur != "WAITING_FOR_APPROVAL":
            job = store.update_fields(
                jid,
                progress_message="Warte auf Freigabe: Interessent",
                capability="crm.prospect_create",
                approval_required="Interessent anlegen",
            )
    except Exception:
        log.exception("prospect_park_approval")
        job = store.update_fields(
            jid,
            progress_message=prompt[:200],
            capability="crm.prospect_create",
        )
    return store.get_job(jid) or job


def execute_prospect_create(
    *,
    job: dict[str, Any],
    turn: dict[str, Any],
    approval_granted: bool = False,
) -> dict[str, Any]:
    jid = job["job_id"]
    collected = dict(turn.get("collected_parameters") or {})

    try:
        if not crm.write_enabled():
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

        company = (collected.get("company") or collected.get("customer") or "").strip()
        contact = (collected.get("contact") or "").strip()
        entity_kind = (collected.get("entity_kind") or "").strip().lower()
        original = (job.get("original_request") or "")[:500]

        if not company:
            prompt = crm_language.ask_company_prompt()
            turn["missing_parameters"] = ["company"]
            turn["state"] = tc.STATE_WAITING_FOR_INPUT
            tc.save(jid, turn)
            return {
                "ok": False,
                "reply": prompt,
                "job": offer_exec._clarify(jid, prompt, turn),
                "turn": turn,
                "terminal": False,
            }

        # CRM requires a Company row — ambiguous person-like names need a clear choice
        if (
            not entity_kind
            and not contact
            and tr.needs_entity_kind_clarification(
                text=original, company_name=company, contact_name=contact
            )
        ):
            collected["pending_person_name"] = company
            collected["company"] = company
            collected["customer"] = company
            turn["collected_parameters"] = collected
            turn["missing_parameters"] = ["entity_kind"]
            turn["state"] = tc.STATE_AWAITING_ENTITY_KIND
            tc.save(jid, turn)
            prompt = (
                f"Ist {company} eine Person beziehungsweise ein Ansprechpartner "
                f"oder soll ich ein Unternehmen mit diesem Namen anlegen?\n"
                "Keine Adresse, E-Mail oder Telefonnummer wird erfunden."
            )
            tr.log_turn_routing(
                chat_id=job.get("telegram_chat_id"),
                job_id=jid,
                current_intent="crm.prospect_create",
                current_entity=company,
                selected_capability="crm.prospect_create",
                guard_result="entity_kind_unclear",
                final_action="clarify_entity_kind",
            )
            return {
                "ok": False,
                "reply": prompt,
                "job": offer_exec._clarify(jid, prompt, turn),
                "turn": turn,
                "terminal": False,
            }

        collected["company"] = company
        collected["customer"] = company
        collected["contact"] = contact
        turn["collected_parameters"] = collected

        if not approval_granted:
            prompt = crm.format_approval(company_name=company, contact_name=contact)
            # Zusage nur mit Job-ID — klare Vorbereitung, keine Fake-Ausführung
            prepared = (
                f"Ich habe den Auftrag zum Anlegen von {company}"
                + (f" (Kontakt: {contact})" if contact else "")
                + " als Interessenten vorbereitet.\n\n"
                + prompt
            )
            job2 = _park_approval(jid, turn, prepared)
            return {
                "ok": False,
                "reply": prepared,
                "job": job2,
                "turn": turn,
                "terminal": False,
                "awaiting_approval": True,
            }

        result = crm.create_prospect(company_name=company, contact_name=contact)
        reply = crm.format_created(result)
        turn["state"] = tc.STATE_DONE
        turn["missing_parameters"] = []
        tc.save(jid, turn)
        out = offer_exec._succeed(
            jid,
            turn,
            reply,
            offer_number=f"prospect:{result.company_id}",
        )
        store.update_fields(
            jid,
            progress_message=(
                "Interessent existiert bereits"
                if result.already_existed
                else "Interessent angelegt"
            ),
            capability="crm.prospect_create",
            external_kind="crm_prospect_create",
            external_last_step=(
                "already_existed" if result.already_existed else "prospect_created"
            ),
            result_reference=f"crm:prospect:{result.company_id}",
        )
        out["job"] = store.get_job(jid) or out["job"]
        return out
    except Exception as e:
        log.exception("crm_prospect_create")
        reply = f"Interessent anlegen fehlgeschlagen: {type(e).__name__}"
        turn["state"] = tc.STATE_FAILED
        tc.save(jid, turn)
        return {
            "ok": False,
            "reply": reply,
            "job": offer_exec._fail(jid, reply, category="crm_write_error"),
            "turn": turn,
            "terminal": True,
        }

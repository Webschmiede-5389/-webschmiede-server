# -*- coding: utf-8 -*-
"""Control plane entry: Stop/Status first, then gated execution pipeline.

Must run BEFORE any LLM processing. Never promises execution without a real job.

Production canary:
  NILS_CONTROL_PLANE=0
  NILS_CONTROL_PLANE_CANARY=1
  NILS_CONTROL_PLANE_ALLOWLIST=<chat_or_user_id>[,…]
Only allowlisted chats/users hit the new plane; everyone else keeps the prior path.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

from nils_job_runtime import control_commands
from nils_job_runtime import crm_offer_exec
from nils_job_runtime import pipeline
from nils_job_runtime import promise_guard
from nils_job_runtime import store
from nils_job_runtime import turn_context as tc
from nils_job_runtime import turn_routing as tr

log = logging.getLogger("nils_job_runtime.control_plane")


def _truthy(name: str, default: str = "0") -> bool:
    return (os.getenv(name, default) or default).lower() not in (
        "0",
        "false",
        "no",
        "off",
        "",
    )


def canary_mode() -> bool:
    return _truthy("NILS_CONTROL_PLANE_CANARY", "0")


def allowlist() -> set[str]:
    raw = (
        os.getenv("NILS_CONTROL_PLANE_ALLOWLIST")
        or os.getenv("NILS_CANARY_TELEGRAM_USER_IDS")
        or ""
    )
    parts = re.split(r"[,;\s]+", raw.strip())
    return {p.strip() for p in parts if p.strip()}


def is_allowlisted(chat_id: str | None, user_id: str | None = None) -> bool:
    allowed = allowlist()
    if not allowed:
        return False
    return str(chat_id or "") in allowed or str(user_id or "") in allowed


def enabled(*, chat_id: str | None = None, user_id: str | None = None) -> bool:
    """
    Production-safe default: OFF.
    Full plane: NILS_CONTROL_PLANE=1
    Canary: NILS_CONTROL_PLANE_CANARY=1 + ALLOWLIST match
    """
    if canary_mode():
        return is_allowlisted(chat_id, user_id)
    return _truthy("NILS_CONTROL_PLANE", "0")


_APPROVAL_YES = re.compile(
    r"(?i)^\s*(?:freigabe\s+)?(?:ja|ok|okay|approve|freigeben)\s*$"
)


def _resume_waiting_input(
    *,
    text: str,
    chat_id: str,
    user_id: str | None,
    message_id: int | None,
) -> dict[str, Any] | None:
    """Continue NEEDS_CLARIFICATION jobs waiting for parameters (no new intent)."""
    active = store.get_single_active_for_chat(str(chat_id))
    if not active or active.get("status") != "NEEDS_CLARIFICATION":
        return None
    turn = tc.load(active)
    if not turn or turn.get("intent") not in (
        tc.INTENT_CRM_GET_OFFER,
        tc.INTENT_CRM_OFFER_PDF,
        tc.INTENT_CRM_CUSTOMER_READ,
        tc.INTENT_CRM_PROSPECT_CREATE,
        tc.INTENT_CRM_EMAIL_SEND,
        tc.INTENT_CRM_INBOUND_READ,
        tc.INTENT_CRM_INBOUND_ACCEPT,
        tc.INTENT_DRIVE,
        *tc.SALES_FIELD_INTENTS,
    ):
        return None
    if not tc.is_waiting(active) and not turn.get("missing_parameters"):
        return None

    # Current-turn-first: cancel waiting job when message is a new distinct task
    mapped_t = pipeline.map_capability(text)
    mapped_cap = mapped_t[0] if mapped_t else None
    prev_ent = tr.previous_entity_from_turn(turn)
    prev_intent = tr.previous_intent_from_turn(turn)
    gate = tr.evaluate_resume_gate(
        text=text,
        mapped_capability=mapped_cap,
        previous_intent=prev_intent,
        previous_entity=prev_ent,
        detect_execution=pipeline.detect_execution_intent(text),
        missing_parameters=list(turn.get("missing_parameters") or []),
    )
    tr.log_turn_routing(
        chat_id=chat_id,
        message_id=message_id,
        job_id=active.get("job_id"),
        current_intent=mapped_cap or gate.current_intent,
        previous_intent=prev_intent,
        current_entity=gate.current_entity,
        previous_entity=prev_ent,
        context_reused=gate.context_reused,
        reuse_reason=gate.reuse_reason,
        selected_capability=mapped_cap or (active.get("capability") or ""),
        guard_result=gate.reason,
        final_action=gate.final_action or gate.action,
    )
    if gate.action == "cancel_and_repipe":
        try:
            store.transition(
                active["job_id"],
                "CANCELLED",
                extra={
                    "finished_at": store.utc_now(),
                    "progress_message": "Ersetzt durch neuen Auftrag (current-turn-first)",
                },
            )
        except Exception:
            log.exception("cancel_waiting_for_restart")
        return None  # fall through to new pipeline

    if gate.action == "block":
        return {
            "ok": False,
            "route": "control_turn_guard",
            "text": (
                "Die aktuelle Nachricht passt nicht zum wartenden Auftrag — "
                "kein stilles Weiterführen mit alter Firma/Entity. "
                "Bitte den Auftrag klar neu formulieren oder „Stop“."
            ),
            "job": store.get_job(active["job_id"]),
            "canary": canary_mode(),
        }

    mapped = mapped_t
    if mapped and mapped[0] in (
        "crm.offer_read",
        "crm.read",
        "crm.offer_pdf_send",
        "crm.customer_read",
        "crm.prospect_create",
        "crm.email_send",
        "crm.pipeline_read",
        "crm.lead_thread",
        "crm.note_create",
        "crm.deal_stage_update",
        "crm.deal_open",
        "crm.offer_write",
        "crm.deal_close",
        "crm.inbound_read",
        "crm.inbound_accept",
        "drive.read",
        "drive.list",
        "drive.doc_create",
        "drive.sheet_create",
        "drive.sheet_write",
        "drive.write",
    ):
        # Safety net (should already cancel via gate)
        try:
            store.transition(
                active["job_id"],
                "CANCELLED",
                extra={
                    "finished_at": store.utc_now(),
                    "progress_message": "Ersetzt durch neuen CRM-Auftrag",
                },
            )
        except Exception:
            log.exception("cancel_waiting_for_restart")
        return None  # fall through to new pipeline

    if mapped or pipeline.detect_execution_intent(text):
        # Different action while waiting — conflict reply via pipeline
        return None

    missing = list(turn.get("missing_parameters") or [])
    t = (text or "").strip()
    if not t:
        return None

    err: str | None = None
    if turn.get("intent") == tc.INTENT_CRM_EMAIL_SEND and missing and missing[0] in (
        "to",
        "subject",
        "body",
    ):
        from nils_job_runtime import crm_email_exec

        turn, err = crm_email_exec.apply_missing_field(turn, t)
    elif turn.get("intent") in tc.SALES_FIELD_INTENTS and missing and missing[0] in (
        "note",
        "stage",
        "outcome",
        "lost_reason",
    ):
        from nils_job_runtime import crm_sales_field_exec as sales_exec

        turn, err = sales_exec.apply_missing_field(turn, t)
    elif missing and missing[0] == "entity_kind":
        collected = dict(turn.get("collected_parameters") or {})
        person_name = (
            collected.get("pending_person_name")
            or collected.get("contact")
            or collected.get("company")
            or ""
        ).strip()
        # „Als Ansprechpartner bei Snack House Yassine.“ → person + company in one turn
        m_ap = re.search(
            r"(?i)(?:als\s+)?(?:ansprechpartner|kontakt)\s+(?:bei|von)\s+(.+?)\s*$",
            t.rstrip(" .!?…"),
        )
        if m_ap:
            company_fill = m_ap.group(1).strip().strip(" .!?\"'")
            collected["entity_kind"] = "person"
            collected["contact"] = person_name
            collected["pending_person_name"] = person_name
            collected["company"] = company_fill
            collected["customer"] = company_fill
            turn["collected_parameters"] = collected
            turn["missing_parameters"] = []
            turn["state"] = tc.STATE_READY_TO_EXECUTE
        else:
            kind = tr.resolve_entity_kind_answer(t)
            if kind == "company":
                collected["entity_kind"] = "company"
                turn["collected_parameters"] = collected
                turn["missing_parameters"] = []
                turn["state"] = tc.STATE_READY_TO_EXECUTE
            elif kind == "person":
                collected["entity_kind"] = "person"
                turn["collected_parameters"] = collected
                # Company still required for CRM data model — ask explicitly
                turn["missing_parameters"] = ["company"]
                turn["state"] = tc.STATE_WAITING_FOR_INPUT
                tc.save(active["job_id"], turn)
                return {
                    "ok": False,
                    "route": "control_crm_prospect_resume",
                    "text": (
                        f"Verstanden — {person_name or 'diese Person'} als Ansprechpartner. "
                        "Zu welchem Unternehmen soll ich den Interessenten anlegen? "
                        "Ich erfinde keine Firma."
                    ),
                    "job": store.get_job(active["job_id"]),
                    "canary": canary_mode(),
                    "resumed": True,
                }
            else:
                err = (
                    "Ist das eine Person beziehungsweise ein Ansprechpartner, "
                    "oder soll ich ein Unternehmen mit diesem Namen anlegen?"
                )
    elif missing and missing[0] in ("customer", "company"):
        # Parameter fill: use extracted company if create-style, else raw text
        fill = pipeline.extract_company_from_text(t) or t
        # Never accept a fill that looks like a create command for a different entity
        if tr.has_create_lexical(t) and tr.primary_entity(t):
            try:
                store.transition(
                    active["job_id"],
                    "CANCELLED",
                    extra={
                        "finished_at": store.utc_now(),
                        "progress_message": "Ersetzt — Create-Lexical statt Param-Fill",
                    },
                )
            except Exception:
                log.exception("cancel_create_during_fill")
            return None
        collected = dict(turn.get("collected_parameters") or {})
        # Person-clarify flow: company answer after entity_kind=person
        if collected.get("entity_kind") == "person" and collected.get("pending_person_name"):
            collected["company"] = fill
            collected["customer"] = fill
            collected["contact"] = collected.get("pending_person_name") or ""
        else:
            collected["company"] = fill
            collected["customer"] = fill
        # offer number in free text?
        onum = pipeline.extract_offer_number_from_text(t)
        if onum:
            collected["offer_number"] = onum
        turn["collected_parameters"] = collected
        turn["missing_parameters"] = []
        turn["state"] = tc.STATE_READY_TO_EXECUTE
    elif missing and missing[0] == "customer_choice":
        turn, err = crm_offer_exec.apply_customer_choice(turn, t)
    elif missing and missing[0] == "offer_choice":
        turn, err = crm_offer_exec.apply_offer_choice(turn, t)
    else:
        # Free-text fallback: treat as company if CRM offer intent waiting
        if turn.get("state") in (
            tc.STATE_WAITING_FOR_INPUT,
            tc.STATE_AWAITING_CUSTOMER_CHOICE,
        ):
            collected = dict(turn.get("collected_parameters") or {})
            if (
                not collected.get("company")
                and not collected.get("customer")
                and not collected.get("company_id")
            ):
                collected["company"] = t
                collected["customer"] = t
                turn["collected_parameters"] = collected
                turn["missing_parameters"] = []
                turn["state"] = tc.STATE_READY_TO_EXECUTE
            elif turn.get("state") == tc.STATE_AWAITING_CUSTOMER_CHOICE:
                turn, err = crm_offer_exec.apply_customer_choice(turn, t)
            else:
                return None
        elif turn.get("state") == tc.STATE_AWAITING_OFFER_CHOICE:
            turn, err = crm_offer_exec.apply_offer_choice(turn, t)
        else:
            return None

    if err:
        tc.save(active["job_id"], turn)
        return {
            "ok": False,
            "route": "control_crm_resume",
            "text": err,
            "job": store.get_job(active["job_id"]),
            "canary": canary_mode(),
        }

    tc.save(active["job_id"], turn)
    is_pdf = turn.get("intent") == tc.INTENT_CRM_OFFER_PDF
    is_customer = turn.get("intent") == tc.INTENT_CRM_CUSTOMER_READ
    if is_pdf:
        from nils_job_runtime import crm_offer_pdf

        result = crm_offer_pdf.resolve_for_pdf(
            job=store.get_job(active["job_id"]) or active,
            turn=turn,
        )
        if result.get("ready"):
            live_raw = os.getenv("NILS_WORKER_LIVE_CAPABILITIES") or ""
            live = {p.strip() for p in live_raw.replace(";", ",").split(",") if p.strip()}
            store.update_fields(
                active["job_id"],
                shadow=0 if "crm.offer_pdf_send" in live else 1,
                task_type="crm.offer_pdf_send",
            )
            queued = crm_offer_pdf.queue_pdf_job(active["job_id"])
            offer = result.get("offer")
            text_out = (
                f"Auftrag {queued['job_id']} angelegt.\n"
                f"Capability: crm.offer_pdf_send\n"
                f"Status: {queued.get('status')}\n"
                f"Angebot: {(offer.offer_number if offer else '–')}\n"
                "PDF wird per Telegram gesendet."
            )
            text_out = promise_guard.sanitize_reply(text_out, job=queued)
            return {
                "ok": True,
                "route": "control_crm_pdf_resume",
                "text": text_out,
                "job": queued,
                "stages": ["INPUT_VALIDATION", "EXECUTION", "FINAL_RESPONSE"],
                "canary": canary_mode(),
                "resumed": True,
            }
        text_out = promise_guard.sanitize_reply(result.get("reply") or "", job=result.get("job"))
        return {
            "ok": bool(result.get("ok")),
            "route": "control_crm_pdf_resume",
            "text": text_out,
            "job": result.get("job"),
            "stages": ["INPUT_VALIDATION", "EXECUTION", "FINAL_RESPONSE"],
            "canary": canary_mode(),
            "resumed": True,
        }

    if is_customer:
        from nils_job_runtime import crm_customer_exec

        result = crm_customer_exec.execute_customer_read(
            job=store.get_job(active["job_id"]) or active,
            turn=turn,
        )
        text_out = promise_guard.sanitize_reply(result["reply"] or "", job=result.get("job"))
        return {
            "ok": bool(result["ok"]),
            "route": "control_crm_customer_resume",
            "text": text_out,
            "job": result.get("job"),
            "stages": ["INPUT_VALIDATION", "EXECUTION", "FINAL_RESPONSE"],
            "canary": canary_mode(),
            "resumed": True,
        }

    if turn.get("intent") == tc.INTENT_CRM_PROSPECT_CREATE:
        from nils_job_runtime import crm_prospect_exec

        result = crm_prospect_exec.execute_prospect_create(
            job=store.get_job(active["job_id"]) or active,
            turn=turn,
            approval_granted=False,
        )
        text_out = promise_guard.sanitize_reply(result["reply"] or "", job=result.get("job"))
        return {
            "ok": bool(result["ok"]),
            "route": "control_crm_prospect_resume",
            "text": text_out,
            "job": result.get("job"),
            "stages": ["INPUT_VALIDATION", "EXECUTION", "FINAL_RESPONSE"],
            "canary": canary_mode(),
            "resumed": True,
        }

    if turn.get("intent") == tc.INTENT_CRM_EMAIL_SEND:
        from nils_job_runtime import crm_email_exec

        result = crm_email_exec.execute_email_send(
            job=store.get_job(active["job_id"]) or active,
            turn=turn,
            approval_granted=False,
        )
        text_out = promise_guard.sanitize_reply(result["reply"] or "", job=result.get("job"))
        return {
            "ok": bool(result["ok"]),
            "route": "control_crm_email_resume",
            "text": text_out,
            "job": result.get("job"),
            "stages": ["INPUT_VALIDATION", "EXECUTION", "FINAL_RESPONSE"],
            "canary": canary_mode(),
            "resumed": True,
        }

    if turn.get("intent") in tc.SALES_FIELD_INTENTS:
        from nils_job_runtime import crm_sales_field_exec as sales_exec

        cap = (store.get_job(active["job_id"]) or active).get("capability") or ""
        intent_to_cap = {v: k for k, v in sales_exec.CAP_TO_INTENT.items()}
        cap = cap if cap in sales_exec.WRITE_CAPS or cap in (
            "crm.pipeline_read",
            "crm.lead_thread",
        ) else intent_to_cap.get(turn.get("intent") or "", "crm.lead_thread")
        result = sales_exec.execute_sales_field(
            job=store.get_job(active["job_id"]) or active,
            turn=turn,
            capability=cap,
            approval_granted=False,
            original_text=t,
        )
        text_out = promise_guard.sanitize_reply(result["reply"] or "", job=result.get("job"))
        return {
            "ok": bool(result["ok"]),
            "route": "control_crm_sales_resume",
            "text": text_out,
            "job": result.get("job"),
            "stages": ["INPUT_VALIDATION", "EXECUTION", "FINAL_RESPONSE"],
            "canary": canary_mode(),
            "resumed": True,
        }

    if turn.get("intent") in (
        tc.INTENT_CRM_INBOUND_READ,
        tc.INTENT_CRM_INBOUND_ACCEPT,
    ):
        from nils_job_runtime import inbound_exec

        cap = (store.get_job(active["job_id"]) or active).get("capability") or (
            "crm.inbound_accept"
            if turn.get("intent") == tc.INTENT_CRM_INBOUND_ACCEPT
            else "crm.inbound_read"
        )
        result = inbound_exec.execute_inbound(
            job=store.get_job(active["job_id"]) or active,
            turn=turn,
            capability=cap,
            approval_granted=False,
            original_text=t,
        )
        text_out = promise_guard.sanitize_reply(result["reply"] or "", job=result.get("job"))
        return {
            "ok": bool(result["ok"]),
            "route": "control_crm_inbound_resume",
            "text": text_out,
            "job": result.get("job"),
            "stages": ["INPUT_VALIDATION", "EXECUTION", "FINAL_RESPONSE"],
            "canary": canary_mode(),
            "resumed": True,
        }

    if turn.get("intent") == tc.INTENT_DRIVE:
        from nils_job_runtime import drive_exec

        cap = (store.get_job(active["job_id"]) or active).get("capability") or "drive.read"
        result = drive_exec.execute_drive(
            job=store.get_job(active["job_id"]) or active,
            turn=turn,
            capability=cap,
            approval_granted=False,
            original_text=t,
        )
        text_out = promise_guard.sanitize_reply(result["reply"] or "", job=result.get("job"))
        return {
            "ok": bool(result["ok"]),
            "route": "control_drive_resume",
            "text": text_out,
            "job": result.get("job"),
            "stages": ["INPUT_VALIDATION", "EXECUTION", "FINAL_RESPONSE"],
            "canary": canary_mode(),
            "resumed": True,
        }

    result = crm_offer_exec.execute_offer_read(
        job=store.get_job(active["job_id"]) or active,
        turn=turn,
    )
    text_out = promise_guard.sanitize_reply(result["reply"] or "", job=result.get("job"))
    return {
        "ok": bool(result["ok"]),
        "route": "control_crm_resume",
        "text": text_out,
        "job": result.get("job"),
        "stages": ["INPUT_VALIDATION", "EXECUTION", "FINAL_RESPONSE"],
        "canary": canary_mode(),
        "resumed": True,
    }


def maybe_handle(
    *,
    text: str,
    chat_id: str,
    user_id: str | None = None,
    message_id: int | None = None,
) -> dict[str, Any] | None:
    if not enabled(chat_id=str(chat_id), user_id=user_id):
        return None
    t = (text or "").strip()
    if not t:
        return None

    ctrl = control_commands.maybe_handle_control_command(
        text=t, chat_id=str(chat_id), user_id=user_id
    )
    if ctrl is not None:
        ctrl["canary"] = canary_mode()
        return ctrl

    # Multi-turn CRM parameter fill BEFORE new-intent gating
    try:
        store.ensure_schema()
        resumed = _resume_waiting_input(
            text=t, chat_id=str(chat_id), user_id=user_id, message_id=message_id
        )
        if resumed is not None:
            return resumed
    except Exception:
        log.exception("control_plane_resume")

    # Prospect pilot: only strict confirm phrases (Ja / Anlegen / Bestätigen)
    try:
        from nils_job_runtime import crm_prospect_pilot as _ppilot

        _prospect_confirm = _ppilot.is_confirm_text(t)
    except Exception:
        _prospect_confirm = bool(_APPROVAL_YES.match(t))

    if _prospect_confirm or _APPROVAL_YES.match(t):
        active = store.get_single_active_for_chat(str(chat_id))
        if active and active.get("status") == "WAITING_FOR_APPROVAL":
            turn = tc.load(active)
            if turn and turn.get("intent") == tc.INTENT_CRM_PROSPECT_CREATE:
                if not _prospect_confirm:
                    return {
                        "ok": False,
                        "route": "control_prospect_confirm_rejected",
                        "text": (
                            "Für Interessenten bitte ausdrücklich bestätigen: "
                            "Ja / Anlegen / Bestätigen / Ja, anlegen — sonst Abbrechen."
                        ),
                        "job": active,
                        "stages": ["APPROVAL_CHECK"],
                        "canary": canary_mode(),
                    }
                from nils_job_runtime import crm_prospect_exec

                result = crm_prospect_exec.execute_prospect_create(
                    job=active,
                    turn=turn,
                    approval_granted=True,
                    confirm_text=t,
                )
                text_out = promise_guard.sanitize_reply(
                    result.get("reply") or "", job=result.get("job")
                )
                return {
                    "ok": bool(result.get("ok")),
                    "route": "control_prospect_approval",
                    "text": text_out,
                    "job": result.get("job"),
                    "stages": ["APPROVAL_CHECK", "EXECUTION", "FINAL_RESPONSE"],
                    "canary": canary_mode(),
                }
            if turn and turn.get("intent") == tc.INTENT_CRM_EMAIL_SEND:
                from nils_job_runtime import crm_email_exec

                result = crm_email_exec.execute_email_send(
                    job=active,
                    turn=turn,
                    approval_granted=True,
                )
                text_out = promise_guard.sanitize_reply(
                    result.get("reply") or "", job=result.get("job")
                )
                return {
                    "ok": bool(result.get("ok")),
                    "route": "control_email_approval",
                    "text": text_out,
                    "job": result.get("job"),
                    "stages": ["APPROVAL_CHECK", "EXECUTION", "FINAL_RESPONSE"],
                    "canary": canary_mode(),
                }
            if turn and turn.get("intent") in tc.SALES_FIELD_INTENTS:
                from nils_job_runtime import crm_sales_field_exec as sales_exec

                cap = active.get("capability") or ""
                intent_to_cap = {v: k for k, v in sales_exec.CAP_TO_INTENT.items()}
                if cap not in sales_exec.CAP_TO_INTENT:
                    cap = intent_to_cap.get(turn.get("intent") or "", "crm.note_create")
                result = sales_exec.execute_sales_field(
                    job=active,
                    turn=turn,
                    capability=cap,
                    approval_granted=True,
                    original_text=active.get("original_request") or t,
                )
                text_out = promise_guard.sanitize_reply(
                    result.get("reply") or "", job=result.get("job")
                )
                return {
                    "ok": bool(result.get("ok")),
                    "route": "control_sales_approval",
                    "text": text_out,
                    "job": result.get("job"),
                    "stages": ["APPROVAL_CHECK", "EXECUTION", "FINAL_RESPONSE"],
                    "canary": canary_mode(),
                }
            if turn and turn.get("intent") == tc.INTENT_CRM_INBOUND_ACCEPT:
                from nils_job_runtime import inbound_exec

                result = inbound_exec.execute_inbound(
                    job=active,
                    turn=turn,
                    capability="crm.inbound_accept",
                    approval_granted=True,
                    original_text=active.get("original_request") or t,
                )
                text_out = promise_guard.sanitize_reply(
                    result.get("reply") or "", job=result.get("job")
                )
                return {
                    "ok": bool(result.get("ok")),
                    "route": "control_inbound_approval",
                    "text": text_out,
                    "job": result.get("job"),
                    "stages": ["APPROVAL_CHECK", "EXECUTION", "FINAL_RESPONSE"],
                    "canary": canary_mode(),
                }
            if turn and turn.get("intent") == "CALENDAR":
                from nils_job_runtime import calendar_exec

                cap = active.get("capability") or "calendar.create"
                result = calendar_exec.execute_calendar(
                    job=active,
                    turn=turn,
                    capability=cap,
                    approval_granted=True,
                    original_text=active.get("original_request") or t,
                )
                text_out = promise_guard.sanitize_reply(
                    result.get("reply") or "", job=result.get("job")
                )
                return {
                    "ok": bool(result.get("ok")),
                    "route": "control_calendar_approval",
                    "text": text_out,
                    "job": result.get("job"),
                    "stages": ["APPROVAL_CHECK", "EXECUTION", "FINAL_RESPONSE"],
                    "canary": canary_mode(),
                }
            if turn and turn.get("intent") == tc.INTENT_DRIVE:
                from nils_job_runtime import drive_exec

                cap = active.get("capability") or "drive.doc_create"
                result = drive_exec.execute_drive(
                    job=active,
                    turn=turn,
                    capability=cap,
                    approval_granted=True,
                    original_text=active.get("original_request") or t,
                )
                text_out = promise_guard.sanitize_reply(
                    result.get("reply") or "", job=result.get("job")
                )
                return {
                    "ok": bool(result.get("ok")),
                    "route": "control_drive_approval",
                    "text": text_out,
                    "job": result.get("job"),
                    "stages": ["APPROVAL_CHECK", "EXECUTION", "FINAL_RESPONSE"],
                    "canary": canary_mode(),
                }
            ctx = pipeline.run_pipeline(
                text=active.get("original_request") or active.get("task_summary") or t,
                chat_id=str(chat_id),
                user_id=user_id,
                message_id=message_id,
                approval_granted=True,
            )
            return {
                "ok": bool(ctx.ok),
                "route": "control_approval",
                "text": ctx.reply,
                "job": ctx.job,
                "stages": ctx.stages_run,
                "canary": canary_mode(),
            }

    mapped = pipeline.map_capability(t)
    if not pipeline.detect_execution_intent(t) and not mapped:
        # CRM execution cues without safe route → block companion LLM fallback
        if tr.has_create_lexical(t) or tr.has_offer_lexical(t):
            tr.log_turn_routing(
                chat_id=chat_id,
                message_id=message_id,
                current_intent="UNMAPPED_CRM",
                current_entity=tr.primary_entity(t),
                context_reused=False,
                guard_result="crm_lexical_unmapped",
                final_action="block_companion_fallback",
            )
            return {
                "ok": False,
                "route": "control_crm_unmapped_block",
                "text": (
                    "CRM-Auftrag erkannt, aber nicht sicher zuordenbar. "
                    "Bitte klar formulieren (Firma/Person + Aktion). "
                    "Kein freier Chat-Fallback."
                ),
                "blocked_reason": "crm_lexical_unmapped",
                "canary": canary_mode(),
            }
        return None

    # Supersede stale active jobs when a new distinct CRM task arrives
    try:
        active_pre = store.get_single_active_for_chat(str(chat_id))
        if active_pre and active_pre.get("status") in (
            "NEEDS_CLARIFICATION",
            "WAITING_FOR_APPROVAL",
            "PREFLIGHT",
            "RECEIVED",
        ):
            turn_pre = tc.load(active_pre)
            prev_ent = tr.previous_entity_from_turn(turn_pre)
            cur_ent = (
                pipeline.extract_company_from_text(t)
                or pipeline.extract_contact_from_text(t)
                or tr.primary_entity(t)
            )
            mapped_cap = mapped[0] if mapped else ""
            same_cap = mapped_cap and mapped_cap == (active_pre.get("capability") or "")
            same_ent = (
                cur_ent
                and prev_ent
                and not tr.entities_conflict(cur_ent, prev_ent)
            )
            # Idempotent duplicate: same prospect create while waiting for approval
            if (
                same_cap
                and same_ent
                and active_pre.get("status") == "WAITING_FOR_APPROVAL"
                and mapped_cap == "crm.prospect_create"
            ):
                tr.log_turn_routing(
                    chat_id=chat_id,
                    message_id=message_id,
                    job_id=active_pre.get("job_id"),
                    current_intent=mapped_cap,
                    previous_intent=tr.previous_intent_from_turn(turn_pre),
                    current_entity=cur_ent,
                    previous_entity=prev_ent,
                    context_reused=True,
                    reuse_reason="idempotent_duplicate",
                    selected_capability=mapped_cap,
                    guard_result="duplicate_suppressed",
                    final_action="return_existing_approval",
                )
                return {
                    "ok": False,
                    "route": "control_prospect_idempotent",
                    "text": (
                        active_pre.get("progress_message")
                        or "Dieser Interessent wartet bereits auf Freigabe. "
                        "Antworte mit „ja“ zum Anlegen oder „Stop“ zum Abbrechen."
                    ),
                    "job": active_pre,
                    "canary": canary_mode(),
                }
            if mapped_cap and (not same_ent or not same_cap or tr.has_create_lexical(t)):
                if not (same_cap and same_ent):
                    try:
                        store.transition(
                            active_pre["job_id"],
                            "CANCELLED",
                            extra={
                                "finished_at": store.utc_now(),
                                "progress_message": "Ersetzt durch neuen Auftrag",
                            },
                        )
                    except Exception:
                        log.exception("cancel_active_for_new_task")
                    tr.log_turn_routing(
                        chat_id=chat_id,
                        message_id=message_id,
                        job_id=active_pre.get("job_id"),
                        current_intent=mapped_cap,
                        previous_intent=tr.previous_intent_from_turn(turn_pre),
                        current_entity=cur_ent,
                        previous_entity=prev_ent,
                        context_reused=False,
                        reuse_reason="superseded_active_job",
                        selected_capability=mapped_cap,
                        guard_result="new_task_cancels_active",
                        final_action="new_job",
                    )
    except Exception:
        log.exception("control_plane_supersede")

    try:
        store.ensure_schema()
        ctx = pipeline.run_pipeline(
            text=t,
            chat_id=str(chat_id),
            user_id=user_id,
            message_id=message_id,
        )
    except Exception as e:
        log.exception("control_plane_pipeline")
        return {
            "ok": False,
            "route": "control_pipeline_error",
            "text": (
                "Steuerung fehlgeschlagen — keine Ausführungszusage. "
                f"Details: {store.redact(str(e), 120)}"
            ),
            "canary": canary_mode(),
        }

    if ctx.route == "passthrough_question":
        return None

    tool_name = (ctx.capability or "") if ctx.capability else ""
    tool_guard = tr.validate_tool_vs_intent(ctx.capability or "", tool_name)
    # Also treat planned capability as tool identity for create↔offer mismatches
    if ctx.capability and mapped:
        tool_guard = tr.validate_tool_vs_intent(mapped[0], ctx.capability)
    if not tool_guard.ok:
        tr.log_turn_routing(
            chat_id=chat_id,
            message_id=message_id,
            job_id=(ctx.job or {}).get("job_id") if ctx.job else None,
            current_intent=mapped[0] if mapped else "",
            selected_capability=ctx.capability or "",
            selected_tool=tool_guard.selected_tool,
            guard_result=tool_guard.reason,
            final_action="block_tool",
        )
        return {
            "ok": False,
            "route": "control_tool_guard",
            "text": (
                "Geplanter Tool-Call passt nicht zum erkannten Intent — "
                "keine Ausführung und keine Tätigkeitszusage."
            ),
            "blocked_reason": tool_guard.reason,
            "canary": canary_mode(),
        }

    cur_ent = (
        (ctx.extracted or {}).get("company")
        if hasattr(ctx, "extracted")
        else None
    ) or pipeline.extract_company_from_text(t) or tr.primary_entity(t)
    tr.log_turn_routing(
        chat_id=chat_id,
        message_id=message_id,
        job_id=(ctx.job or {}).get("job_id") if ctx.job else None,
        current_intent=ctx.capability or (mapped[0] if mapped else ""),
        current_entity=cur_ent or "",
        context_reused=False,
        reuse_reason="fresh_turn",
        selected_capability=ctx.capability or "",
        selected_tool=ctx.capability or "",
        guard_result=ctx.blocked_reason or "pipeline_ok",
        final_action="pipeline_reply",
    )

    text_out = promise_guard.sanitize_reply(ctx.reply or "", job=ctx.job)
    return {
        "ok": bool(ctx.ok),
        "route": ctx.route if ctx.route != "pipeline" else "control_pipeline",
        "text": text_out,
        "job": ctx.job,
        "stages": ctx.stages_run,
        "blocked_reason": ctx.blocked_reason or None,
        "canary": canary_mode(),
    }


def guard_outgoing_reply(reply: str, *, chat_id: str | None = None) -> str:
    job = None
    if chat_id:
        try:
            job = store.get_single_active_for_chat(str(chat_id))
        except Exception:
            job = None
    return promise_guard.sanitize_reply(reply, job=job)


def feature_flags_public() -> dict[str, Any]:
    al = allowlist()
    return {
        "NILS_CONTROL_PLANE": _truthy("NILS_CONTROL_PLANE", "0"),
        "NILS_CONTROL_PLANE_CANARY": canary_mode(),
        "allowlist_count": len(al),
        "allowlist_masks": [("..." + x[-4:]) if len(x) >= 4 else "***" for x in sorted(al)],
    }

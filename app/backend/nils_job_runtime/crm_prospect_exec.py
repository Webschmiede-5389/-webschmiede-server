# -*- coding: utf-8 -*-
"""Execute CRM prospect create after bound preview + explicit confirmation."""
from __future__ import annotations

import logging
import os
from typing import Any

from nils_job_runtime import crm_language
from nils_job_runtime import crm_offer_exec as offer_exec
from nils_job_runtime import crm_prospect_pilot as pilot
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


def _audit_base(job: dict[str, Any], turn: dict[str, Any]) -> dict[str, Any]:
    collected = turn.get("collected_parameters") or {}
    binding = collected.get("pilot_binding") or {}
    return {
        "release_id": os.getenv("NILS_RELEASE_ID") or "",
        "commit": (os.getenv("NILS_GIT_COMMIT") or "")[:40],
        "chat_id": str(job.get("telegram_chat_id") or "")[-4:],
        "owner_id": str(binding.get("owner_id") or job.get("telegram_user_id") or "")[-4:],
        "message_id": job.get("telegram_message_id"),
        "job_id": job.get("job_id"),
        "intent": "crm.prospect_create",
        "entity": collected.get("company") or "",
        "selected_capability": "crm.prospect_create",
        "selected_tool": "crm.prospect_create",
        "tenant_id": os.getenv("NILS_CRM_TENANT_ID") or "",
        "preview_payload_hash": (binding.get("payload_hash") or "")[:16],
    }


def execute_prospect_create(
    *,
    job: dict[str, Any],
    turn: dict[str, Any],
    approval_granted: bool = False,
    confirm_text: str = "",
) -> dict[str, Any]:
    jid = job["job_id"]
    collected = dict(turn.get("collected_parameters") or {})
    chat_id = str(job.get("telegram_chat_id") or "")
    owner_id = str(job.get("telegram_user_id") or chat_id)

    try:
        if not crm.write_enabled() or pilot.pilot_exhausted():
            if pilot.pilot_exhausted() and crm.write_enabled():
                pilot.disable_capability("exhausted_gate")
            reply = "Diese Aktion kann ich aktuell noch nicht ausführen."
            turn["state"] = tc.STATE_FAILED
            tc.save(jid, turn)
            pilot.audit_event(
                {
                    **_audit_base(job, turn),
                    "action": "cap_off",
                    "guard_result": "cap_or_pilot_exhausted",
                    "final_action": "block",
                }
            )
            return {
                "ok": False,
                "reply": reply,
                "job": offer_exec._fail(jid, reply, category="cap_off"),
                "turn": turn,
                "terminal": True,
            }

        company = (collected.get("company") or collected.get("customer") or "").strip()
        contact = (collected.get("contact") or "").strip()
        email = (collected.get("email") or "").strip()
        phone = (collected.get("phone") or "").strip()
        entity_kind = (collected.get("entity_kind") or "").strip().lower()
        original = (job.get("original_request") or "")[:500]
        # Country / legal_basis only from explicit text or prior collected values
        country = (collected.get("country") or "").strip() or pilot.extract_country_from_text(
            original
        )
        legal_basis = (
            collected.get("legal_basis") or ""
        ).strip() or pilot.extract_legal_basis_from_text(original)
        # Storage ≠ marketing: outbound never auto-on for Nils create
        outbound_allowed = False
        if (collected.get("outbound_allowed") or "").strip().lower() in (
            "1",
            "true",
            "yes",
            "ja",
        ):
            # only if a separate approved process set this flag on the turn
            outbound_allowed = True

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

        payload = pilot.payload_dict(
            company=company,
            contact=contact,
            email=email,
            phone=phone,
            country=country,
            legal_basis=legal_basis,
            outbound_allowed="true" if outbound_allowed else "false",
        )
        company = payload["company"]
        contact = payload["contact"]
        country = payload.get("country") or ""
        legal_basis = payload.get("legal_basis") or ""
        collected["company"] = company
        collected["customer"] = company
        collected["contact"] = contact
        collected["country"] = country
        collected["legal_basis"] = legal_basis
        collected["outbound_allowed"] = payload.get("outbound_allowed") or "false"
        turn["collected_parameters"] = collected

        # Duplicate check before preview and before write
        dup = pilot.find_duplicate_candidates(
            company_name=company,
            email=email,
            phone=phone,
            contact_name=contact,
        )
        if dup["result"] == "exact" and dup.get("exact"):
            reply = pilot.format_duplicate_exact(dup["exact"])
            turn["state"] = tc.STATE_DONE
            tc.save(jid, turn)
            pilot.audit_event(
                {
                    **_audit_base(job, turn),
                    "action": "duplicate_exact",
                    "duplicate_result": "exact",
                    "candidate_matches": [dup["exact"]],
                    "record_id": dup["exact"].get("id"),
                    "final_action": "no_write",
                    "guard_result": "duplicate_exact",
                }
            )
            out = offer_exec._succeed(
                jid,
                turn,
                reply,
                offer_number=f"prospect:{dup['exact']['id']}",
            )
            store.update_fields(
                jid,
                progress_message="Interessent existiert bereits",
                capability="crm.prospect_create",
                external_kind="crm_prospect_create",
                external_last_step="already_existed",
                result_reference=f"crm:prospect:{dup['exact']['id']}",
            )
            out["job"] = store.get_job(jid) or out["job"]
            return out

        if dup["result"] == "uncertain" and not approval_granted:
            reply = pilot.format_duplicate_uncertain(dup.get("fuzzy") or [])
            turn["missing_parameters"] = ["company"]
            turn["state"] = tc.STATE_WAITING_FOR_INPUT
            tc.save(jid, turn)
            pilot.audit_event(
                {
                    **_audit_base(job, turn),
                    "action": "duplicate_uncertain",
                    "duplicate_result": "uncertain",
                    "candidate_matches": (dup.get("fuzzy") or [])[:5],
                    "final_action": "ask",
                    "guard_result": "duplicate_uncertain",
                }
            )
            return {
                "ok": False,
                "reply": reply,
                "job": offer_exec._clarify(jid, reply, turn),
                "turn": turn,
                "terminal": False,
            }

        if not approval_granted:
            binding = pilot.bind_preview(
                turn,
                chat_id=chat_id,
                owner_id=owner_id,
                job_id=jid,
                payload=payload,
            )
            prompt = pilot.format_preview(payload)
            job2 = _park_approval(jid, turn, prompt)
            pilot.audit_event(
                {
                    **_audit_base(job2, turn),
                    "action": "preview",
                    "duplicate_result": dup["result"],
                    "candidate_matches": (dup.get("fuzzy") or [])[:3],
                    "confirmation_state": "awaiting",
                    "preview_payload_hash": binding["payload_hash"][:16],
                    "final_action": "preview",
                    "guard_result": "preview_bound",
                }
            )
            return {
                "ok": False,
                "reply": prompt,
                "job": job2,
                "turn": turn,
                "terminal": False,
                "awaiting_approval": True,
            }

        ok_c, reason, binding = pilot.validate_confirmation(
            turn,
            chat_id=chat_id,
            owner_id=owner_id,
            job_id=jid,
            text=confirm_text or "ja",
        )
        if not ok_c:
            if reason == "confirmation_expired":
                reply = (
                    "Die Bestätigung ist abgelaufen (max. 10 Minuten). "
                    "Bitte den Auftrag erneut starten — ich zeige eine neue Vorschau."
                )
                try:
                    store.transition(
                        jid,
                        "CANCELLED",
                        extra={
                            "finished_at": store.utc_now(),
                            "progress_message": "confirmation_expired",
                        },
                    )
                except Exception:
                    pass
            elif reason == "payload_changed":
                reply = (
                    "Zwischen Vorschau und Bestätigung hat sich etwas geändert. "
                    "Ich erstelle eine neue Vorschau."
                )
                # Fall through to new preview
                return execute_prospect_create(
                    job=store.get_job(jid) or job,
                    turn=turn,
                    approval_granted=False,
                )
            else:
                reply = (
                    "Bestätigung ungültig oder nicht an diese Vorschau gebunden. "
                    "Bitte mit Ja / Anlegen / Bestätigen antworten, oder Abbrechen."
                )
            pilot.audit_event(
                {
                    **_audit_base(job, turn),
                    "action": "confirm_rejected",
                    "confirmation_state": reason,
                    "guard_result": reason,
                    "final_action": "no_write",
                }
            )
            if reason == "confirmation_expired":
                turn["state"] = tc.STATE_FAILED
                tc.save(jid, turn)
                return {
                    "ok": False,
                    "reply": reply,
                    "job": store.get_job(jid) or job,
                    "turn": turn,
                    "terminal": True,
                }
            return {
                "ok": False,
                "reply": reply,
                "job": job,
                "turn": turn,
                "terminal": False,
            }

        # Re-check duplicates immediately before write
        dup2 = pilot.find_duplicate_candidates(
            company_name=company,
            email=email,
            phone=phone,
            contact_name=contact,
        )
        if dup2["result"] == "exact" and dup2.get("exact"):
            reply = pilot.format_duplicate_exact(dup2["exact"])
            turn["state"] = tc.STATE_DONE
            tc.save(jid, turn)
            pilot.audit_event(
                {
                    **_audit_base(job, turn),
                    "action": "duplicate_before_write",
                    "duplicate_result": "exact",
                    "record_id": dup2["exact"].get("id"),
                    "final_action": "no_write",
                }
            )
            out = offer_exec._succeed(
                jid, turn, reply, offer_number=f"prospect:{dup2['exact']['id']}"
            )
            out["job"] = store.get_job(jid) or out["job"]
            return out

        before_count = _company_count()
        pilot.mark_confirmed(turn)
        tc.save(jid, turn)

        # Write exactly the confirmed preview payload
        bound = (binding or {}).get("payload") or payload
        company = bound.get("company") or company
        contact = bound.get("contact") or contact
        country = bound.get("country") or ""
        legal_basis = bound.get("legal_basis") or ""
        outbound_allowed = (bound.get("outbound_allowed") or "false").lower() == "true"

        result = crm.create_prospect(
            company_name=company,
            contact_name=contact,
            country=country or None,
            legal_basis=legal_basis or None,
            outbound_allowed=bool(outbound_allowed),
        )
        after_count = _company_count()

        # Side-effect / safety checks
        life = str(getattr(result, "lifecycle_status", "") or "").upper()
        if life and life != "PROSPECT":
            pilot.emergency_stop(f"wrong_lifecycle:{life}")
            reply = "Sicherheitsstopp: unerwarteter Lifecycle. Capability deaktiviert."
            return {
                "ok": False,
                "reply": reply,
                "job": offer_exec._fail(jid, reply, category="pilot_safety"),
                "turn": turn,
                "terminal": True,
            }
        if (
            not result.already_existed
            and after_count != before_count + 1
        ):
            pilot.emergency_stop(
                f"count_mismatch:{before_count}->{after_count}"
            )
            reply = "Sicherheitsstopp: Datensatz-Count unerwartet. Capability deaktiviert."
            return {
                "ok": False,
                "reply": reply,
                "job": offer_exec._fail(jid, reply, category="pilot_safety"),
                "turn": turn,
                "terminal": True,
            }

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

        if not result.already_existed:
            n = pilot.record_success(
                record_id=int(result.company_id),
                company=company,
                job_id=jid,
            )
            reply = reply + f"\n\nPilot-Stand: {n}/{pilot.pilot_max()} Anlagen."
            out["reply"] = reply

        pilot.audit_event(
            {
                **_audit_base(out["job"], turn),
                "action": "write",
                "confirmation_state": "confirmed",
                "confirmation_timestamp": (binding or {}).get("confirmed_at"),
                "duplicate_result": dup2["result"],
                "record_id": result.company_id,
                "already_existed": bool(result.already_existed),
                "count_before": before_count,
                "count_after": after_count,
                "side_effects": {
                    "mail": False,
                    "n8n": False,
                    "deal": False,
                    "offer": False,
                    "customer": False,
                },
                "final_action": "created" if not result.already_existed else "idempotent",
                "guard_result": "write_ok",
                "pilot_count": pilot.success_count(),
            }
        )
        out["reply"] = reply
        return out
    except Exception as e:
        log.exception("crm_prospect_create")
        pilot.emergency_stop(f"write_error:{type(e).__name__}")
        reply = f"Interessent anlegen fehlgeschlagen: {type(e).__name__}. Capability deaktiviert."
        turn["state"] = tc.STATE_FAILED
        tc.save(jid, turn)
        pilot.audit_event(
            {
                **_audit_base(job, turn),
                "action": "write_error",
                "guard_result": type(e).__name__,
                "final_action": "emergency_stop",
            }
        )
        return {
            "ok": False,
            "reply": reply,
            "job": offer_exec._fail(jid, reply, category="crm_write_error"),
            "turn": turn,
            "terminal": True,
        }


def _company_count() -> int:
    from nils_job_runtime import crm_offer_service as offer_svc

    con = offer_svc._connect(readonly=True)
    try:
        row = con.execute(
            "SELECT COUNT(*) AS n FROM companies WHERE tenant_id = ?",
            (offer_svc.tenant_id(),),
        ).fetchone()
        return int(row["n"] if row else 0)
    finally:
        con.close()

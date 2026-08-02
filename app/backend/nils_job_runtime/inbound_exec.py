# -*- coding: utf-8 -*-
"""Execute Inbound list / accept (Zug D)."""
from __future__ import annotations

import logging
import re
from typing import Any

from nils_job_runtime import crm_offer_exec as offer_exec
from nils_job_runtime import inbound_notify as inn
from nils_job_runtime import inbound_service as inbound
from nils_job_runtime import store
from nils_job_runtime import turn_context as tc

log = logging.getLogger("nils_job_runtime.inbound_exec")


def _park_approval(jid: str, turn: dict[str, Any], prompt: str) -> dict[str, Any]:
    turn["state"] = tc.STATE_AWAITING_SALES_APPROVAL
    tc.save(jid, turn)
    try:
        job = store.get_job(jid)
        assert job
        cur = job["status"]
        if cur == "RECEIVED":
            job = store.transition(
                jid, "PREFLIGHT", extra={"pipeline_stage": "APPROVAL_CHECK"}
            )
            cur = job["status"]
        if cur == "PREFLIGHT":
            store.transition(
                jid,
                "WAITING_FOR_APPROVAL",
                extra={
                    "approval_required": "crm.inbound_accept",
                    "capability": "crm.inbound_accept",
                    "progress_message": "Warte auf Freigabe: Inbound annehmen",
                },
            )
        else:
            store.update_fields(
                jid,
                progress_message=prompt[:200],
                capability="crm.inbound_accept",
                approval_required="crm.inbound_accept",
            )
    except Exception:
        log.exception("inbound_park_approval")
    return store.get_job(jid) or {}


def execute_inbound(
    *,
    job: dict[str, Any],
    turn: dict[str, Any],
    capability: str,
    approval_granted: bool = False,
    original_text: str = "",
) -> dict[str, Any]:
    jid = job["job_id"]
    text = original_text or (job.get("original_request") or "")

    if not inbound.enabled():
        reply = "Inbound ist aktuell deaktiviert."
        turn["state"] = tc.STATE_FAILED
        tc.save(jid, turn)
        return {
            "ok": False,
            "reply": reply,
            "job": offer_exec._fail(jid, reply, category="cap_off"),
            "turn": turn,
            "terminal": True,
        }

    if capability == "crm.inbound_read":
        leads = inbound.list_pending()
        reply = inbound.format_list(leads)
        turn["state"] = tc.STATE_DONE
        tc.save(jid, turn)
        return offer_exec._succeed(jid, turn, reply, offer_number="inbound:list")

    # Annehmen
    collected = dict(turn.get("collected_parameters") or {})
    parsed = None
    if collected.get("inbound_kind") and collected.get("inbound_id"):
        parsed = (str(collected["inbound_kind"]), int(collected["inbound_id"]))
    else:
        raw = inn.parse_lead_ref(text)
        if raw:
            parsed = raw
    if not parsed:
        turn["missing_parameters"] = ["lead_ref"]
        turn["state"] = tc.STATE_WAITING_FOR_INPUT
        prompt = (
            "Welchen Lead annehmen?\n"
            "Beispiel: Annehmen meta:12  oder  Annehmen email:5\n"
            "Liste: „Inbound“"
        )
        tc.save(jid, turn)
        return {
            "ok": False,
            "reply": prompt,
            "job": offer_exec._clarify(jid, prompt, turn),
            "turn": turn,
            "terminal": False,
        }

    kind, lid = parsed
    try:
        lead = inbound.get_lead(kind, lid)
    except PermissionError as e:
        reply = str(e)
        turn["state"] = tc.STATE_FAILED
        tc.save(jid, turn)
        return {
            "ok": False,
            "reply": reply,
            "job": offer_exec._fail(jid, reply, category="tenant"),
            "turn": turn,
            "terminal": True,
        }
    if not lead:
        reply = f"Lead {kind}:{lid} nicht gefunden."
        turn["state"] = tc.STATE_FAILED
        tc.save(jid, turn)
        return {
            "ok": False,
            "reply": reply,
            "job": offer_exec._fail(jid, reply, category="not_found"),
            "turn": turn,
            "terminal": True,
        }

    collected["inbound_kind"] = kind
    collected["inbound_id"] = lid
    collected["lead_ref"] = lead["ref"]
    turn["collected_parameters"] = collected

    if not approval_granted:
        prompt = inbound.format_approval(lead)
        _park_approval(jid, turn, prompt)
        return {
            "ok": False,
            "reply": prompt,
            "job": store.get_job(jid) or job,
            "turn": turn,
            "terminal": False,
        }

    try:
        result = inbound.accept_lead(kind, lid)
    except Exception as e:
        log.exception("inbound_accept")
        reply = f"Annehmen fehlgeschlagen: {type(e).__name__}: {e}"
        turn["state"] = tc.STATE_FAILED
        tc.save(jid, turn)
        return {
            "ok": False,
            "reply": reply,
            "job": offer_exec._fail(jid, reply, category="inbound_accept"),
            "turn": turn,
            "terminal": True,
        }

    reply = inbound.format_accepted(result)
    turn["state"] = tc.STATE_DONE
    tc.save(jid, turn)
    return offer_exec._succeed(
        jid, turn, reply, offer_number=f"inbound:{lead['ref']}"
    )

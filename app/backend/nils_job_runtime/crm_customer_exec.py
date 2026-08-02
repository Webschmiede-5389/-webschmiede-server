# -*- coding: utf-8 -*-
"""Execute CRM company/contact/onboarding read (inline, no writes)."""
from __future__ import annotations

import logging
from typing import Any

from nils_job_runtime import crm_customer_service as crm
from nils_job_runtime import crm_language
from nils_job_runtime import crm_offer_exec as offer_exec
from nils_job_runtime import store
from nils_job_runtime import turn_context as tc

log = logging.getLogger("nils_job_runtime.crm_customer_exec")


def execute_customer_read(*, job: dict[str, Any], turn: dict[str, Any]) -> dict[str, Any]:
    jid = job["job_id"]
    collected = dict(turn.get("collected_parameters") or {})

    try:
        probe = crm.probe()
        if not probe.get("ok"):
            reply = (
                "CRM ist gerade nicht erreichbar — ich kann keine Kundendaten laden. "
                f"({probe.get('detail') or probe.get('outcome')})"
            )
            turn["state"] = tc.STATE_FAILED
            tc.save(jid, turn)
            return {
                "ok": False,
                "reply": reply,
                "job": offer_exec._fail(jid, reply, category="crm_unreachable"),
                "turn": turn,
                "terminal": True,
            }

        company_id = collected.get("company_id")
        company_query = (
            collected.get("company") or collected.get("customer") or ""
        ).strip()

        if not company_id:
            if not company_query:
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
            hits = crm.search_companies(company_query)
            if not hits:
                reply = crm_language.company_not_found(company_query)
                turn["state"] = tc.STATE_FAILED
                tc.save(jid, turn)
                return {
                    "ok": False,
                    "reply": reply,
                    "job": offer_exec._fail(jid, reply, category="customer_not_found"),
                    "turn": turn,
                    "terminal": True,
                }
            if len(hits) > 1:
                exact = [h for h in hits if h.name.lower() == company_query.lower()]
                if len(exact) != 1:
                    cand = [
                        {
                            "id": h.id,
                            "name": h.name,
                            "customer_number": h.customer_number,
                        }
                        for h in hits
                    ]
                    turn["candidates"] = {"companies": cand}
                    turn["missing_parameters"] = ["customer_choice"]
                    turn["state"] = tc.STATE_AWAITING_CUSTOMER_CHOICE
                    reply = crm.format_company_choices(hits)
                    tc.save(jid, turn)
                    return {
                        "ok": False,
                        "reply": reply,
                        "job": offer_exec._clarify(jid, reply, turn),
                        "turn": turn,
                        "terminal": False,
                    }
                hits = exact
            company_id = hits[0].id
            collected["company_id"] = company_id
            collected["company"] = hits[0].name
            collected["customer"] = hits[0].name
            turn["collected_parameters"] = collected

        from nils_job_runtime import crm_offer_service as offer_svc

        profile = crm.get_company_profile(int(company_id))
        if not profile or int(profile.company.tenant_id) != int(offer_svc.tenant_id()):
            reply = "Unternehmen nicht gefunden oder falscher Tenant."
            turn["state"] = tc.STATE_FAILED
            tc.save(jid, turn)
            return {
                "ok": False,
                "reply": reply,
                "job": offer_exec._fail(jid, reply, category="tenant_or_missing"),
                "turn": turn,
                "terminal": True,
            }

        reply = crm.format_profile(profile)
        turn["state"] = tc.STATE_DONE
        turn["missing_parameters"] = []
        tc.save(jid, turn)
        return offer_exec._succeed(
            jid, turn, reply, offer_number=f"company:{profile.company.id}"
        )
    except Exception as e:
        log.exception("crm_customer_read")
        reply = f"CRM-Lesen fehlgeschlagen: {type(e).__name__}"
        turn["state"] = tc.STATE_FAILED
        tc.save(jid, turn)
        return {
            "ok": False,
            "reply": reply,
            "job": offer_exec._fail(jid, reply, category="crm_error"),
            "turn": turn,
            "terminal": True,
        }


def apply_customer_choice(turn: dict[str, Any], text: str) -> tuple[dict[str, Any], str | None]:
    return offer_exec.apply_customer_choice(turn, text)

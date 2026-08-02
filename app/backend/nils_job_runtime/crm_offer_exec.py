# -*- coding: utf-8 -*-
"""Execute CRM offer read for an active/resumed multi-turn job (inline, no worker queue)."""
from __future__ import annotations

import logging
import re
from typing import Any

from nils_job_runtime import crm_language
from nils_job_runtime import crm_offer_service as crm
from nils_job_runtime import store
from nils_job_runtime import turn_context as tc

log = logging.getLogger("nils_job_runtime.crm_offer_exec")


def _eur_ok(reply: str) -> bool:
    return "€" in reply or "Positionen" in reply


def resolve_customer_selection(text: str, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    t = (text or "").strip()
    if not t or not candidates:
        return None
    if re.fullmatch(r"\d+", t):
        idx = int(t) - 1
        if 0 <= idx < len(candidates):
            return candidates[idx]
    low = t.lower()
    exact = [c for c in candidates if str(c.get("name", "")).lower() == low]
    if len(exact) == 1:
        return exact[0]
    num = [c for c in candidates if str(c.get("customer_number", "")).lower() == low]
    if len(num) == 1:
        return num[0]
    return None


def resolve_offer_selection(
    text: str, candidates: list[dict[str, Any]]
) -> dict[str, Any] | None:
    t = (text or "").strip()
    if not t or not candidates:
        return None
    if re.fullmatch(r"\d+", t):
        idx = int(t) - 1
        if 0 <= idx < len(candidates):
            return candidates[idx]
    low = t.lower()
    by_num = [c for c in candidates if str(c.get("offer_number", "")).lower() == low]
    if len(by_num) == 1:
        return by_num[0]
    return None


def execute_offer_read(
    *,
    job: dict[str, Any],
    turn: dict[str, Any],
) -> dict[str, Any]:
    """
    Run CRM customer/offer resolution and return:
      {ok, reply, job, turn, terminal}
    Never queues a worker job.
    """
    jid = job["job_id"]
    collected = dict(turn.get("collected_parameters") or {})
    candidates = dict(turn.get("candidates") or {})

    # --- awaiting choices ---
    if turn.get("state") == tc.STATE_AWAITING_CUSTOMER_CHOICE:
        # filled by resume with free text already in collected or via selection key
        pass

    company_id = collected.get("company_id")
    customer_query = (
        collected.get("company") or collected.get("customer") or ""
    ).strip()

    try:
        probe = crm.probe()
        if not probe.get("ok"):
            reply = (
                "CRM ist gerade nicht erreichbar — ich kann kein Angebot laden. "
                f"({probe.get('detail') or probe.get('outcome')})"
            )
            turn["state"] = tc.STATE_FAILED
            turn["missing_parameters"] = []
            tc.save(jid, turn)
            job = _fail(jid, reply, category="crm_unreachable")
            return {"ok": False, "reply": reply, "job": job, "turn": turn, "terminal": True}

        # Offer number alone (tenant-scoped) — before company prompt
        offer_number = (collected.get("offer_number") or "").strip()
        if offer_number and not company_id and not collected.get("offer_id"):
            hits = crm.list_offers_by_number(offer_number)
            if not hits:
                reply = f"Kein Angebot {offer_number} im CRM gefunden."
                turn["state"] = tc.STATE_FAILED
                turn["missing_parameters"] = []
                tc.save(jid, turn)
                job = _fail(jid, reply, category="offer_missing")
                return {"ok": False, "reply": reply, "job": job, "turn": turn, "terminal": True}
            if len(hits) > 1:
                companies = {h.company_id for h in hits}
                if len(companies) > 1:
                    cand = [
                        {
                            "id": o.id,
                            "offer_number": o.offer_number,
                            "status": o.status,
                            "created_at": o.created_at,
                            "total": o.total_display_eur,
                        }
                        for o in hits
                    ]
                    turn["candidates"] = {**candidates, "offers": cand}
                    turn["missing_parameters"] = ["offer_choice"]
                    turn["state"] = tc.STATE_AWAITING_OFFER_CHOICE
                    reply = crm.format_offer_choices(hits)
                    tc.save(jid, turn)
                    job = _clarify(jid, reply, turn)
                    return {
                        "ok": False,
                        "reply": reply,
                        "job": job,
                        "turn": turn,
                        "terminal": False,
                    }
            offer = hits[0]
            reply = crm.format_offer(offer)
            return _succeed(jid, turn, reply, offer_number=offer.offer_number)

        # Resolve company
        if not company_id:
            if not customer_query:
                prompt = crm_language.ask_company_prompt()
                turn["missing_parameters"] = ["company"]
                turn["state"] = tc.STATE_WAITING_FOR_INPUT
                tc.save(jid, turn)
                job = _clarify(jid, prompt, turn)
                return {
                    "ok": False,
                    "reply": prompt,
                    "job": job,
                    "turn": turn,
                    "terminal": False,
                }

            hits = crm.search_companies(customer_query)
            if not hits:
                reply = crm_language.company_not_found(customer_query)
                turn["state"] = tc.STATE_FAILED
                turn["missing_parameters"] = []
                tc.save(jid, turn)
                job = _fail(jid, reply, category="customer_not_found")
                return {"ok": False, "reply": reply, "job": job, "turn": turn, "terminal": True}

            if len(hits) > 1:
                cand = [
                    {
                        "id": h.id,
                        "name": h.name,
                        "customer_number": h.customer_number,
                    }
                    for h in hits
                ]
                # Prefer exact name match
                exact = [h for h in hits if h.name.lower() == customer_query.lower()]
                if len(exact) == 1:
                    hits = exact
                else:
                    turn["candidates"] = {"companies": cand}
                    turn["missing_parameters"] = ["customer_choice"]
                    turn["state"] = tc.STATE_AWAITING_CUSTOMER_CHOICE
                    reply = crm.format_company_choices(hits)
                    tc.save(jid, turn)
                    job = _clarify(jid, reply, turn)
                    return {
                        "ok": False,
                        "reply": reply,
                        "job": job,
                        "turn": turn,
                        "terminal": False,
                    }

            company_id = hits[0].id
            collected["company_id"] = company_id
            collected["company"] = hits[0].name
            collected["customer"] = hits[0].name  # legacy alias
            turn["collected_parameters"] = collected

        # Explicit offer id from prior selection
        if collected.get("offer_id"):
            offer = crm.get_offer(int(collected["offer_id"]))
            if not offer:
                reply = "Angebot nicht mehr gefunden."
                turn["state"] = tc.STATE_FAILED
                tc.save(jid, turn)
                job = _fail(jid, reply, category="offer_missing")
                return {
                    "ok": False,
                    "reply": reply,
                    "job": job,
                    "turn": turn,
                    "terminal": True,
                }
            reply = crm.format_offer(offer)
            return _succeed(jid, turn, reply, offer_number=offer.offer_number)

        # Offer selection pending?
        if turn.get("missing_parameters") == ["offer_choice"] or turn.get("state") == tc.STATE_AWAITING_OFFER_CHOICE:
            offer_sel = collected.get("offer_choice") or collected.get("offer_id")
            offers_cand = candidates.get("offers") or []
            if offer_sel is not None and offers_cand:
                chosen = None
                if isinstance(offer_sel, int) or (isinstance(offer_sel, str) and offer_sel.isdigit()):
                    chosen = resolve_offer_selection(str(offer_sel), offers_cand)
                else:
                    chosen = resolve_offer_selection(str(offer_sel), offers_cand)
                if not chosen:
                    reply = "Auswahl nicht erkannt. Bitte Nummer oder Angebotsnummer."
                    turn["missing_parameters"] = ["offer_choice"]
                    turn["state"] = tc.STATE_AWAITING_OFFER_CHOICE
                    tc.save(jid, turn)
                    job = _clarify(jid, reply, turn)
                    return {
                        "ok": False,
                        "reply": reply,
                        "job": job,
                        "turn": turn,
                        "terminal": False,
                    }
                offer = crm.get_offer(int(chosen["id"]))
                if not offer:
                    reply = "Angebot nicht mehr gefunden."
                    turn["state"] = tc.STATE_FAILED
                    tc.save(jid, turn)
                    job = _fail(jid, reply, category="offer_missing")
                    return {
                        "ok": False,
                        "reply": reply,
                        "job": job,
                        "turn": turn,
                        "terminal": True,
                    }
                reply = crm.format_offer(offer)
                return _succeed(jid, turn, reply, offer_number=offer.offer_number)

        offers = crm.list_offers(int(company_id))
        if not offers:
            co_name = collected.get("company") or collected.get("customer") or "dieses Unternehmen"
            reply = crm.format_no_offer(str(co_name))
            turn["state"] = tc.STATE_FAILED
            turn["missing_parameters"] = []
            tc.save(jid, turn)
            job = _fail(jid, reply, category="no_offers")
            return {"ok": False, "reply": reply, "job": job, "turn": turn, "terminal": True}

        if len(offers) > 1:
            cand = [
                {
                    "id": o.id,
                    "offer_number": o.offer_number,
                    "status": o.status,
                    "created_at": o.created_at,
                    "total": o.total_display_eur,
                }
                for o in offers
            ]
            turn["candidates"] = {**candidates, "offers": cand}
            turn["missing_parameters"] = ["offer_choice"]
            turn["state"] = tc.STATE_AWAITING_OFFER_CHOICE
            reply = crm.format_offer_choices(offers)
            tc.save(jid, turn)
            job = _clarify(jid, reply, turn)
            return {
                "ok": False,
                "reply": reply,
                "job": job,
                "turn": turn,
                "terminal": False,
            }

        offer = offers[0]
        reply = crm.format_offer(offer)
        assert _eur_ok(reply)
        return _succeed(jid, turn, reply, offer_number=offer.offer_number)

    except FileNotFoundError as e:
        reply = f"CRM ist nicht erreichbar ({e})."
        turn["state"] = tc.STATE_FAILED
        tc.save(jid, turn)
        job = _fail(jid, reply, category="crm_unreachable")
        return {"ok": False, "reply": reply, "job": job, "turn": turn, "terminal": True}
    except Exception as e:
        log.exception("crm_offer_read")
        reply = f"CRM-Lesen fehlgeschlagen: {type(e).__name__}"
        turn["state"] = tc.STATE_FAILED
        tc.save(jid, turn)
        job = _fail(jid, reply, category="crm_error")
        return {"ok": False, "reply": reply, "job": job, "turn": turn, "terminal": True}


def apply_customer_choice(turn: dict[str, Any], text: str) -> tuple[dict[str, Any], str | None]:
    """Apply free-text / index selection for customer. Returns (turn, error_reply)."""
    cands = (turn.get("candidates") or {}).get("companies") or []
    chosen = resolve_customer_selection(text, cands)
    if not chosen:
        return turn, "Auswahl nicht erkannt. Bitte Nummer oder exakten Namen."
    collected = dict(turn.get("collected_parameters") or {})
    collected["company_id"] = int(chosen["id"])
    collected["company"] = chosen["name"]
    collected["customer"] = chosen["name"]  # legacy alias
    turn["collected_parameters"] = collected
    turn["missing_parameters"] = []
    turn["state"] = tc.STATE_READY_TO_EXECUTE
    return turn, None


def apply_offer_choice(turn: dict[str, Any], text: str) -> tuple[dict[str, Any], str | None]:
    cands = (turn.get("candidates") or {}).get("offers") or []
    chosen = resolve_offer_selection(text, cands)
    if not chosen:
        return turn, "Auswahl nicht erkannt. Bitte Nummer oder Angebotsnummer."
    collected = dict(turn.get("collected_parameters") or {})
    collected["offer_id"] = int(chosen["id"])
    collected["offer_choice"] = str(chosen.get("offer_number") or chosen["id"])
    turn["collected_parameters"] = collected
    turn["missing_parameters"] = []
    turn["state"] = tc.STATE_READY_TO_EXECUTE
    return turn, None


def _clarify(job_id: str, reply: str, turn: dict[str, Any]) -> dict[str, Any]:
    job = store.get_job(job_id)
    assert job
    if job["status"] != "NEEDS_CLARIFICATION":
        try:
            if job["status"] in ("RECEIVED", "PREFLIGHT"):
                job = store.transition(
                    job_id,
                    "NEEDS_CLARIFICATION",
                    extra={"progress_message": reply[:200], "pipeline_stage": "INPUT_VALIDATION"},
                )
        except Exception:
            log.exception("clarify_transition")
    tc.save(job_id, turn)
    return store.update_fields(
        job_id,
        progress_message=reply[:200],
        capability=job.get("capability") or "crm.offer_read",
        pipeline_stage="INPUT_VALIDATION",
    )


def _fail(job_id: str, reply: str, *, category: str) -> dict[str, Any]:
    job = store.get_job(job_id)
    assert job
    try:
        if job["status"] not in store.TERMINAL if hasattr(store, "TERMINAL") else ():
            pass
    except Exception:
        pass
    from nils_job_runtime.model import TERMINAL

    if job["status"] not in TERMINAL:
        # path to FAILED
        cur = job["status"]
        try:
            if cur == "NEEDS_CLARIFICATION":
                job = store.transition(
                    job_id,
                    "FAILED",
                    extra={
                        "finished_at": store.utc_now(),
                        "error_category": category,
                        "error_message_redacted": store.redact(reply, 200),
                        "progress_message": reply[:200],
                    },
                )
            elif cur in ("RECEIVED", "PREFLIGHT"):
                job = store.transition(
                    job_id,
                    "FAILED",
                    extra={
                        "finished_at": store.utc_now(),
                        "error_category": category,
                        "error_message_redacted": store.redact(reply, 200),
                    },
                )
            elif cur == "QUEUED":
                job = store.transition(
                    job_id,
                    "FAILED",
                    extra={
                        "finished_at": store.utc_now(),
                        "error_category": category,
                        "error_message_redacted": store.redact(reply, 200),
                    },
                )
            else:
                job = store.update_fields(
                    job_id,
                    error_category=category,
                    error_message_redacted=store.redact(reply, 200),
                )
        except Exception:
            log.exception("fail_transition")
            job = store.update_fields(
                job_id,
                error_category=category,
                error_message_redacted=store.redact(reply, 200),
            )
    return store.get_job(job_id) or job


def _succeed(
    job_id: str, turn: dict[str, Any], reply: str, *, offer_number: str
) -> dict[str, Any]:
    turn["state"] = tc.STATE_DONE
    turn["missing_parameters"] = []
    tc.save(job_id, turn)
    job = store.get_job(job_id)
    assert job
    # Prefer SUCCEEDED via allowed path: … → QUEUED → RUNNING → SUCCEEDED is heavy.
    # Use COMPLETED/SUCCEEDED from current status.
    from nils_job_runtime.model import TERMINAL, can_transition

    try:
        cur = job["status"]
        if cur not in TERMINAL and can_transition(cur, "SUCCEEDED"):
            job = store.transition(
                job_id,
                "SUCCEEDED",
                extra={
                    "finished_at": store.utc_now(),
                    "result_reference": f"crm:offer:{offer_number}",
                    "progress_message": "CRM-Angebot angezeigt",
                    "pipeline_stage": "FINAL_RESPONSE",
                    "external_kind": "crm_offer_read",
                    "external_last_step": "offer_loaded",
                },
            )
        elif cur not in TERMINAL:
            job = store.update_fields(
                job_id,
                result_reference=f"crm:offer:{offer_number}",
                progress_message="CRM-Angebot angezeigt",
            )
    except Exception:
        log.exception("succeed_transition")
        job = store.update_fields(
            job_id,
            result_reference=f"crm:offer:{offer_number}",
            progress_message="CRM-Angebot angezeigt",
        )

    job = store.get_job(job_id) or job
    return {
        "ok": True,
        "reply": reply,
        "job": job,
        "turn": turn,
        "terminal": True,
    }

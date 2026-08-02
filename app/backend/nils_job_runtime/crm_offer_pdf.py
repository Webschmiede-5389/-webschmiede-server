# -*- coding: utf-8 -*-
"""CRM offer PDF resolve + Telegram send (read-only CRM, no writes)."""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from nils_job_runtime import crm_language
from nils_job_runtime import crm_offer_service as crm
from nils_job_runtime import offer_pdf
from nils_job_runtime import store
from nils_job_runtime import turn_context as tc

log = logging.getLogger("nils_job_runtime.crm_offer_pdf")

MAX_PDF_BYTES = int(os.getenv("NILS_OFFER_PDF_MAX_BYTES", str(20 * 1024 * 1024)) or (20 * 1024 * 1024))


def resolve_for_pdf(*, job: dict[str, Any], turn: dict[str, Any]) -> dict[str, Any]:
    """
    Resolve company/offer for PDF send.
    Returns {ok, reply, job, turn, terminal, offer} — never writes CRM.
    """
    from nils_job_runtime import crm_offer_exec as read_exec

    jid = job["job_id"]
    collected = dict(turn.get("collected_parameters") or {})
    candidates = dict(turn.get("candidates") or {})

    try:
        probe = crm.probe()
        if not probe.get("ok"):
            reply = (
                "CRM ist gerade nicht erreichbar — ich kann kein PDF senden. "
                f"({probe.get('detail') or probe.get('outcome')})"
            )
            turn["state"] = tc.STATE_FAILED
            tc.save(jid, turn)
            return {
                "ok": False,
                "reply": reply,
                "job": read_exec._fail(jid, reply, category="crm_unreachable"),
                "turn": turn,
                "terminal": True,
                "offer": None,
            }

        offer_number = (collected.get("offer_number") or "").strip()
        offer_id = collected.get("offer_id")
        company_id = collected.get("company_id")
        company_query = (
            collected.get("company") or collected.get("customer") or ""
        ).strip()

        # Direct offer id
        if offer_id:
            offer = crm.get_offer(int(offer_id))
            if not offer or int(offer.tenant_id) != int(crm.tenant_id()):
                reply = "Angebot nicht gefunden oder falscher Tenant."
                turn["state"] = tc.STATE_FAILED
                tc.save(jid, turn)
                return {
                    "ok": False,
                    "reply": reply,
                    "job": read_exec._fail(jid, reply, category="offer_missing"),
                    "turn": turn,
                    "terminal": True,
                    "offer": None,
                }
            return _ready(jid, turn, offer)

        # Offer number (tenant-scoped)
        if offer_number and not company_id:
            hits = crm.list_offers_by_number(offer_number)
            if not hits:
                reply = f"Kein Angebot {offer_number} im CRM gefunden."
                turn["state"] = tc.STATE_FAILED
                tc.save(jid, turn)
                return {
                    "ok": False,
                    "reply": reply,
                    "job": read_exec._fail(jid, reply, category="offer_missing"),
                    "turn": turn,
                    "terminal": True,
                    "offer": None,
                }
            if len(hits) > 1:
                # same number multiple versions — pick latest already ordered; still ask if companies differ
                companies = {h.company_id for h in hits}
                if len(companies) > 1:
                    cand = [
                        {
                            "id": h.id,
                            "offer_number": h.offer_number,
                            "status": h.status,
                            "created_at": h.created_at,
                            "total": h.total_display_eur,
                            "company_name": h.company_name,
                        }
                        for h in hits
                    ]
                    turn["candidates"] = {**candidates, "offers": cand}
                    turn["missing_parameters"] = ["offer_choice"]
                    turn["state"] = tc.STATE_AWAITING_OFFER_CHOICE
                    reply = crm.format_offer_choices(hits)
                    tc.save(jid, turn)
                    return {
                        "ok": False,
                        "reply": reply,
                        "job": read_exec._clarify(jid, reply, turn),
                        "turn": turn,
                        "terminal": False,
                        "offer": None,
                    }
            return _ready(jid, turn, hits[0])

        # Company resolution
        if not company_id:
            if not company_query and not offer_number:
                prompt = crm_language.ask_company_prompt()
                turn["missing_parameters"] = ["company"]
                turn["state"] = tc.STATE_WAITING_FOR_INPUT
                tc.save(jid, turn)
                return {
                    "ok": False,
                    "reply": prompt,
                    "job": read_exec._clarify(jid, prompt, turn),
                    "turn": turn,
                    "terminal": False,
                    "offer": None,
                }
            if company_query:
                hits = crm.search_companies(company_query)
                if not hits:
                    reply = crm_language.company_not_found(company_query)
                    turn["state"] = tc.STATE_FAILED
                    tc.save(jid, turn)
                    return {
                        "ok": False,
                        "reply": reply,
                        "job": read_exec._fail(jid, reply, category="customer_not_found"),
                        "turn": turn,
                        "terminal": True,
                        "offer": None,
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
                            "job": read_exec._clarify(jid, reply, turn),
                            "turn": turn,
                            "terminal": False,
                            "offer": None,
                        }
                    hits = exact
                company_id = hits[0].id
                collected["company_id"] = company_id
                collected["company"] = hits[0].name
                collected["customer"] = hits[0].name
                turn["collected_parameters"] = collected

        # Offer selection pending
        if turn.get("state") == tc.STATE_AWAITING_OFFER_CHOICE:
            offer_sel = collected.get("offer_choice") or collected.get("offer_id")
            offers_cand = candidates.get("offers") or []
            if offer_sel is not None and offers_cand:
                chosen = read_exec.resolve_offer_selection(str(offer_sel), offers_cand)
                if not chosen:
                    reply = "Auswahl nicht erkannt. Bitte Nummer oder Angebotsnummer."
                    turn["missing_parameters"] = ["offer_choice"]
                    turn["state"] = tc.STATE_AWAITING_OFFER_CHOICE
                    tc.save(jid, turn)
                    return {
                        "ok": False,
                        "reply": reply,
                        "job": read_exec._clarify(jid, reply, turn),
                        "turn": turn,
                        "terminal": False,
                        "offer": None,
                    }
                offer = crm.get_offer(int(chosen["id"]))
                if not offer:
                    reply = "Angebot nicht mehr gefunden."
                    turn["state"] = tc.STATE_FAILED
                    tc.save(jid, turn)
                    return {
                        "ok": False,
                        "reply": reply,
                        "job": read_exec._fail(jid, reply, category="offer_missing"),
                        "turn": turn,
                        "terminal": True,
                        "offer": None,
                    }
                return _ready(jid, turn, offer)

        assert company_id
        if offer_number:
            offer = crm.get_offer_by_number(int(company_id), offer_number)
            if not offer:
                co_name = collected.get("company") or company_query or "dieses Unternehmen"
                reply = crm.format_no_offer(str(co_name))
                turn["state"] = tc.STATE_FAILED
                tc.save(jid, turn)
                return {
                    "ok": False,
                    "reply": reply,
                    "job": read_exec._fail(jid, reply, category="no_offers"),
                    "turn": turn,
                    "terminal": True,
                    "offer": None,
                }
            return _ready(jid, turn, offer)

        offers = crm.list_offers(int(company_id))
        if not offers:
            co_name = collected.get("company") or company_query or "dieses Unternehmen"
            reply = crm.format_no_offer(str(co_name))
            turn["state"] = tc.STATE_FAILED
            tc.save(jid, turn)
            return {
                "ok": False,
                "reply": reply,
                "job": read_exec._fail(jid, reply, category="no_offers"),
                "turn": turn,
                "terminal": True,
                "offer": None,
            }
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
            return {
                "ok": False,
                "reply": reply,
                "job": read_exec._clarify(jid, reply, turn),
                "turn": turn,
                "terminal": False,
                "offer": None,
            }
        return _ready(jid, turn, offers[0])

    except Exception as e:
        log.exception("crm_offer_pdf_resolve")
        reply = f"PDF-Vorbereitung fehlgeschlagen: {type(e).__name__}"
        turn["state"] = tc.STATE_FAILED
        tc.save(jid, turn)
        return {
            "ok": False,
            "reply": reply,
            "job": read_exec._fail(jid, reply, category="pdf_resolve_error"),
            "turn": turn,
            "terminal": True,
            "offer": None,
        }


def _ready(jid: str, turn: dict[str, Any], offer: Any) -> dict[str, Any]:
    collected = dict(turn.get("collected_parameters") or {})
    collected["offer_id"] = int(offer.id)
    collected["company_id"] = int(offer.company_id) if offer.company_id is not None else None
    collected["offer_number"] = offer.offer_number
    collected["company"] = offer.company_name
    collected["tenant_id"] = int(offer.tenant_id)
    turn["collected_parameters"] = collected
    turn["missing_parameters"] = []
    turn["state"] = tc.STATE_READY_TO_EXECUTE
    tc.save(jid, turn)
    store.update_fields(
        jid,
        capability="crm.offer_pdf_send",
        external_kind="crm_offer_pdf",
        external_ref=f"offer_id={offer.id};num={offer.offer_number}",
        progress_message=f"PDF bereit für {offer.offer_number}",
    )
    return {
        "ok": True,
        "reply": "",
        "job": store.get_job(jid),
        "turn": turn,
        "terminal": False,
        "offer": offer,
        "ready": True,
    }


def queue_pdf_job(job_id: str) -> dict[str, Any]:
    """Move resolved PDF job to QUEUED (live shadow=0)."""
    job = store.get_job(job_id)
    assert job
    store.update_fields(job_id, shadow=0, task_type="crm.offer_pdf_send")
    cur = job["status"]
    if cur in ("RECEIVED", "NEEDS_CLARIFICATION"):
        if cur == "NEEDS_CLARIFICATION":
            # path: clarify → PREFLIGHT not always allowed; try PREFLIGHT then QUEUED
            try:
                from nils_job_runtime.model import can_transition

                if can_transition(cur, "PREFLIGHT"):
                    job = store.transition(job_id, "PREFLIGHT", extra={"pipeline_stage": "JOB_CREATION"})
                    cur = "PREFLIGHT"
            except Exception:
                log.exception("pdf_preflight")
        if cur == "RECEIVED":
            job = store.transition(job_id, "PREFLIGHT", extra={"pipeline_stage": "JOB_CREATION"})
            cur = "PREFLIGHT"
    if cur == "PREFLIGHT":
        job = store.transition(
            job_id,
            "QUEUED",
            extra={
                "queued_at": store.utc_now(),
                "pipeline_stage": "JOB_CREATION",
                "progress_message": "PDF-Versand in Warteschlange",
                "shadow": 0,
            },
        )
    return store.get_job(job_id) or job


def execute_pdf_send(job: dict[str, Any], wid: str) -> dict[str, Any]:
    """Worker handler: render PDF + Telegram sendDocument."""
    from nils_job_runtime import queue as q

    jid = job["job_id"]
    chat_id = job.get("telegram_chat_id")
    turn = tc.load(job) or {}
    collected = dict(turn.get("collected_parameters") or {})
    offer_id = collected.get("offer_id")
    if not offer_id:
        raise RuntimeError("pdf_missing_offer_id")

    q.heartbeat(jid, wid=wid, current_step="crm_read", progress_message="Angebot laden")
    offer = crm.get_offer(int(offer_id))
    if not offer:
        raise RuntimeError("offer_not_found")
    if int(offer.tenant_id) != int(crm.tenant_id()):
        raise RuntimeError("tenant_mismatch")

    q.heartbeat(jid, wid=wid, current_step="pdf_render", progress_message="PDF erzeugen")
    tmpdir = Path(tempfile.mkdtemp(prefix="nils-offer-pdf-"))
    fname = offer_pdf.safe_filename(
        offer_number=offer.offer_number, company_name=offer.company_name
    )
    pdf_path = tmpdir / fname
    try:
        offer_pdf.render_offer_pdf(offer, dest=pdf_path)
        size = pdf_path.stat().st_size
        if size <= 0:
            raise RuntimeError("pdf_empty")
        if size > MAX_PDF_BYTES:
            raise RuntimeError("pdf_too_large")

        q.heartbeat(
            jid,
            wid=wid,
            current_step="telegram_send",
            progress_message="PDF per Telegram senden",
        )
        import telegram_ops as tg

        caption = (
            f"Angebot {offer.offer_number} — {offer.company_name}\n"
            f"Status: {offer.status}"
        )
        sent = tg.send_document(
            chat_id,
            str(pdf_path),
            filename=fname,
            caption=caption,
        )
        if not sent.get("ok"):
            raise RuntimeError(f"telegram_send_failed:{sent.get('error') or 'unknown'}")

        store.update_fields(
            jid,
            external_last_step="document_sent",
            result_reference=f"crm:offer_pdf:{offer.offer_number}:{fname}",
            progress_message=f"PDF {fname} gesendet",
        )
        return {
            "result_reference": f"crm:offer_pdf:{offer.offer_number}",
            "filename": fname,
            "offer_number": offer.offer_number,
            "company_name": offer.company_name,
        }
    finally:
        try:
            if pdf_path.exists():
                pdf_path.unlink()
            tmpdir.rmdir()
        except Exception:
            log.exception("pdf_temp_cleanup")

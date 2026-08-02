# -*- coding: utf-8 -*-
"""Current-turn-first / entity-leak / prospect routing guards (A–J).

Isolated: no production CRM writes, no Telegram, no deploy.
"""
from __future__ import annotations

import os
import sys
import tempfile
import traceback
from pathlib import Path

TMP = tempfile.mkdtemp(prefix="nils-turn-route-")
DB = Path(TMP) / "nils-runtime.db"
CRM_DB = Path(TMP) / "nils-crm.db"
os.environ["NILS_RUNTIME_DB"] = str(DB)
os.environ["NILS_CRM_DB"] = str(CRM_DB)
os.environ["NILS_CRM_BACKEND"] = "sqlite"
os.environ["NILS_CRM_TENANT_ID"] = "1"
os.environ["NILS_CONTROL_PLANE"] = "1"
os.environ["NILS_CONTROL_PLANE_STAGING"] = "1"
os.environ["NILS_JOB_NOTIFY"] = "0"
os.environ["NILS_CAP_CRM_READ"] = "1"
os.environ["NILS_CAP_CRM_OFFER_PDF"] = "1"
os.environ["NILS_CAP_CRM_PROSPECT_CREATE"] = "1"
os.environ["NILS_CAP_EMAIL_SEND"] = "0"
os.environ["NILS_CAP_N8N"] = "0"
os.environ["NILS_WORKER_LIVE_CAPABILITIES"] = (
    "crm.offer_read,crm.offer_pdf_send,crm.customer_read,crm.prospect_create"
)
os.environ.pop("NILS_CRM_DATABASE_URL", None)
os.environ.pop("NILS_WRITE_ENABLED", None)

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from nils_job_runtime import control_plane, promise_guard, store  # noqa: E402
from nils_job_runtime import crm_offer_service as crm  # noqa: E402
from nils_job_runtime import pipeline  # noqa: E402
from nils_job_runtime import turn_context as tc  # noqa: E402
from nils_job_runtime import turn_routing as tr  # noqa: E402

CHAT = "turn-route-chat"
UID = "turn-route-user"
RESULTS: list[tuple[str, str, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, "PASS" if cond else "FAIL", (detail or "")[:320]))
    print(("PASS" if cond else "FAIL"), name, (detail or "")[:220])


def webhook(text: str, *, mid: int = 0, chat_id: str = CHAT) -> dict:
    return (
        control_plane.maybe_handle(
            text=text, chat_id=chat_id, user_id=UID, message_id=mid or None
        )
        or {}
    )


def cancel_active(chat_id: str = CHAT) -> None:
    act = store.get_single_active_for_chat(chat_id)
    if act:
        try:
            store.transition(
                act["job_id"], "CANCELLED", extra={"finished_at": store.utc_now()}
            )
        except Exception:
            pass


def main() -> int:
    store.ensure_schema()
    crm.seed_isolated_fixture(CRM_DB, reset=True)
    mid = 7100

    # --- Intent mapping evidence (root-cause regression) ---
    msg_a = "Lege Hassan Yassine als potentieller Kunde an"
    check(
        "map_hassan_prospect",
        pipeline.map_capability(msg_a) == ("crm.prospect_create", "write"),
        str(pipeline.map_capability(msg_a)),
    )
    check(
        "extract_hassan",
        pipeline.extract_company_from_text(msg_a) == "Hassan Yassine",
        pipeline.extract_company_from_text(msg_a),
    )

    # --- A: prior offer mbp → new create Hassan (no mbp leak) ---
    mid += 1
    r0 = webhook("Zeig mir das Angebot von MBP Service.", mid=mid)
    check(
        "A0_offer_mbp",
        r0.get("ok") is True and "mbp" in (r0.get("text") or "").lower(),
        (r0.get("text") or "")[:180],
    )
    mid += 1
    r_a = webhook(msg_a, mid=mid)
    txt_a = r_a.get("text") or ""
    job_a = r_a.get("job") or {}
    check(
        "A_no_mbp_leak",
        "mbp" not in txt_a.lower()
        and "krefeld" not in txt_a.lower()
        and "angebot" not in txt_a.lower()
        and "dokument" not in txt_a.lower(),
        txt_a[:220],
    )
    check(
        "A_prospect_or_clarify",
        (
            "Hassan Yassine" in txt_a
            and (
                "person" in txt_a.lower()
                or "ansprechpartner" in txt_a.lower()
                or "interessent" in txt_a.lower()
                or job_a.get("capability") == "crm.prospect_create"
                or (job_a.get("status") in ("NEEDS_CLARIFICATION", "WAITING_FOR_APPROVAL"))
            )
        ),
        f"status={job_a.get('status')} cap={job_a.get('capability')} text={txt_a[:180]}",
    )
    check(
        "A_not_offer_path",
        (job_a.get("capability") or "") != "crm.offer_read"
        and (r_a.get("route") or "") != "control_crm_resume",
        f"route={r_a.get('route')} cap={job_a.get('capability')}",
    )

    # --- B: backref may reuse mbp (nur ohne dazwischenliegenden Create) ---
    cancel_active()
    mid += 1
    r_b0 = webhook("Zeig mir das Angebot von MBP Service.", mid=mid)
    check("B0_seed", r_b0.get("ok") is True, (r_b0.get("text") or "")[:120])
    mid += 1
    r_b = webhook("Zeig mir das Angebot noch einmal", mid=mid)
    txt_b = r_b.get("text") or ""
    check(
        "B_backref_reuses_mbp",
        r_b.get("ok") is True
        and ("mbp" in txt_b.lower() or "ang-" in txt_b.lower()),
        txt_b[:220],
    )

    # --- B2 / Canary-C: Create beendet Angebotskontext → keine stille mbp-Reuse ---
    cancel_active()
    mid += 1
    webhook("Zeig mir das Angebot von MBP Service.", mid=mid)
    mid += 1
    webhook(msg_a, mid=mid)  # create breaks offer context
    mid += 1
    r_c_back = webhook("Zeig mir das Angebot noch einmal", mid=mid)
    txt_cb = (r_c_back.get("text") or "").lower()
    check(
        "C_no_silent_mbp_after_create",
        "mbp" not in txt_cb
        and (
            "welche" in txt_cb
            or "firma" in txt_cb
            or "kontakt" in txt_cb
            or (r_c_back.get("job") or {}).get("status") == "NEEDS_CLARIFICATION"
        ),
        (r_c_back.get("text") or "")[:220],
    )

    # --- C: Firma A then Firma B create ---
    cancel_active()
    mid += 1
    webhook("Zeig mir das Angebot von MBP Service.", mid=mid)
    mid += 1
    r_c = webhook("Lege Firma B als Interessenten an", mid=mid)
    txt_c = r_c.get("text") or ""
    check(
        "C_only_firma_b",
        "Firma B" in txt_c and "mbp" not in txt_c.lower() and "MBP" not in txt_c,
        txt_c[:220],
    )

    # --- D: Lege Hassan Yassine an → person/company clarify ---
    cancel_active()
    mid += 1
    r_d = webhook("Lege Hassan Yassine an", mid=mid)
    txt_d = r_d.get("text") or ""
    check(
        "D_entity_kind_ask",
        "Hassan Yassine" in txt_d
        and (
            "person" in txt_d.lower()
            or "ansprechpartner" in txt_d.lower()
            or "unternehmen" in txt_d.lower()
        ),
        txt_d[:220],
    )

    # --- E: Ansprechpartner bei Firma ---
    cancel_active()
    mid += 1
    r_e = webhook(
        "Lege Hassan Yassine als Ansprechpartner bei Snack House Yassine an",
        mid=mid,
    )
    txt_e = r_e.get("text") or ""
    check(
        "E_person_and_company",
        "Hassan Yassine" in txt_e
        and "Snack House Yassine" in txt_e
        and (r_e.get("job") or {}).get("status") == "WAITING_FOR_APPROVAL",
        f"status={(r_e.get('job') or {}).get('status')} text={txt_e[:200]}",
    )

    # --- F: old waiting job_id + new entity → new job (no silent resume) ---
    cancel_active()
    mid += 1
    r_f0 = webhook("Zeig mir das Angebot aus dem CRM.", mid=mid)
    old_job = (r_f0.get("job") or {}).get("job_id")
    check(
        "F0_waiting",
        (r_f0.get("job") or {}).get("status") == "NEEDS_CLARIFICATION",
        f"status={(r_f0.get('job') or {}).get('status')} text={(r_f0.get('text') or '')[:120]}",
    )
    mid += 1
    r_f = webhook(msg_a, mid=mid)
    new_job = (r_f.get("job") or {}).get("job_id")
    check(
        "F_new_job_not_reuse",
        bool(new_job) and new_job != old_job and "mbp" not in (r_f.get("text") or "").lower(),
        f"old={old_job} new={new_job} text={(r_f.get('text') or '')[:160]}",
    )
    old_row = store.get_job(old_job) if old_job else None
    check(
        "F_old_cancelled",
        old_row is None or old_row.get("status") == "CANCELLED",
        str((old_row or {}).get("status")),
    )

    # --- G: CREATE intent vs GET_OFFER tool ---
    g = tr.validate_tool_vs_intent("crm.prospect_create", "crm.offer_read")
    check("G_tool_guard_blocks", g.ok is False and g.action == "block", str(g))
    g2 = tr.validate_intent_consistency(msg_a, "crm.offer_read")
    check("G_intent_guard_blocks", g2.ok is False, str(g2))

    # --- H: entity not in message, no backref ---
    h = tr.validate_entity_against_message(
        "Lege Hassan Yassine als Interessenten an",
        "mbp Service GmbH",
        allow_backref=True,
    )
    check("H_stale_entity_blocked", h.ok is False, str(h))
    h2 = tr.validate_entity_against_message(
        "Zeig mir das Angebot noch einmal",
        "mbp Service GmbH",
        allow_backref=True,
    )
    check("H_backref_allows", h2.ok is True and h2.context_reused, str(h2))

    # --- I: write capability off ---
    cancel_active()
    os.environ["NILS_CAP_CRM_PROSPECT_CREATE"] = "0"
    mid += 1
    r_i = webhook("Lege Canary WriteOff GmbH als Interessenten an", mid=mid)
    txt_i = r_i.get("text") or ""
    check(
        "I_cap_off_honest",
        promise_guard.CAPABILITY_DISABLED_TEXT in txt_i
        or "noch nicht" in txt_i.lower(),
        txt_i[:200],
    )
    check(
        "I_no_exec_promise",
        not promise_guard.contains_live_promise(txt_i)
        or promise_guard.CAPABILITY_DISABLED_TEXT in txt_i,
        txt_i[:160],
    )
    os.environ["NILS_CAP_CRM_PROSPECT_CREATE"] = "1"

    # --- J: duplicate identical message → no uncontrolled second write job ---
    cancel_active()
    mid += 1
    # Force company-like name to skip entity-kind and reach approval
    r_j1 = webhook("Lege Duplikat Test GmbH als Interessenten an", mid=mid)
    j1 = (r_j1.get("job") or {}).get("job_id")
    mid += 1
    r_j2 = webhook("Lege Duplikat Test GmbH als Interessenten an", mid=mid)
    j2 = (r_j2.get("job") or {}).get("job_id")
    check(
        "J_idempotent_same_job",
        bool(j1)
        and j1 == j2
        and (r_j2.get("route") in ("control_prospect_idempotent", "control_pipeline")
             or (r_j2.get("job") or {}).get("status") == "WAITING_FOR_APPROVAL"),
        f"j1={j1} j2={j2} route={r_j2.get('route')} status={(r_j2.get('job') or {}).get('status')}",
    )

    # Promise guard covers the observed false reply pattern
    fake = (
        "Verstanden: du willst das Angebot für die mbp Service GmbH in Krefeld sehen. "
        "Ich schau jetzt im CRM nach und hol dir das Dokument."
    )
    cleaned = promise_guard.sanitize_reply(fake, job=None)
    check(
        "promise_guard_schau_jetzt",
        cleaned == promise_guard.NO_ACCESS_TEXT
        or "keinen funktionsfähigen" in cleaned.lower()
        or "Zusage entfernt" in cleaned,
        cleaned[:180],
    )

    # Residual: Müller Dach regression
    check(
        "regress_mueller_extract",
        pipeline.extract_company_from_text(
            "Leg Müller Dach GmbH mit Peter Müller an"
        )
        == "Müller Dach GmbH",
        pipeline.extract_company_from_text(
            "Leg Müller Dach GmbH mit Peter Müller an"
        ),
    )

    # Ansprechpartner ohne Firma → Intent + fehlende Company
    cancel_active()
    mid += 1
    r_max = webhook("Lege Max Mustermann als Ansprechpartner an.", mid=mid)
    check(
        "F_max_maps_prospect",
        pipeline.map_capability("Lege Max Mustermann als Ansprechpartner an.")
        == ("crm.prospect_create", "write")
        and pipeline.extract_contact_from_text(
            "Lege Max Mustermann als Ansprechpartner an."
        )
        == "Max Mustermann"
        and not pipeline.extract_company_from_text(
            "Lege Max Mustermann als Ansprechpartner an."
        ),
        str(pipeline.map_capability("Lege Max Mustermann als Ansprechpartner an.")),
    )
    tmax = (r_max.get("text") or "").lower()
    check(
        "F_max_asks_company",
        "firma" in tmax or "unternehmen" in tmax or "kontakt" in tmax,
        (r_max.get("text") or "")[:200],
    )

    # Companion fallback block
    cancel_active()
    mid += 1
    r_fb = webhook("xyzzy lege an ohne klaren namen", mid=mid)
    check(
        "companion_fallback_blocked",
        (r_fb.get("route") == "control_crm_unmapped_block")
        or "nicht sicher" in (r_fb.get("text") or "").lower(),
        f"route={r_fb.get('route')} text={(r_fb.get('text') or '')[:160]}",
    )

    failed = [x for x in RESULTS if x[1] == "FAIL"]
    print("\n=== SUMMARY ===")
    print(f"passed={len(RESULTS) - len(failed)} failed={len(failed)} total={len(RESULTS)}")
    for name, st, detail in RESULTS:
        if st == "FAIL":
            print("FAIL", name, detail)
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)

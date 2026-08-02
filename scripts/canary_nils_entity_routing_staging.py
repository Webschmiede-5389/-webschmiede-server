# -*- coding: utf-8 -*-
"""Final staging canary A–H: Current-Turn-First entity routing (isolated sqlite).

Requires fresh NILS_CRM_DB (new file). No production writes. No mid-canary hotfixes.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path("/root/app/backend")
os.chdir(BACKEND)
sys.path.insert(0, str(BACKEND))

for line in Path(".env").read_text(encoding="utf-8").splitlines():
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, _, v = line.partition("=")
    os.environ[k.strip()] = v

RELEASE_ID = (os.environ.get("NILS_RELEASE_ID") or os.environ.get("NILS_RUNTIME_CODE_VERSION") or "").strip()
COMMIT_ID = (os.environ.get("NILS_GIT_COMMIT") or "").strip()

os.environ["NILS_CONTROL_PLANE"] = "1"
os.environ["NILS_CONTROL_PLANE_CANARY"] = "0"
os.environ["NILS_CONTROL_PLANE_STAGING"] = "1"
os.environ["NILS_JOB_NOTIFY"] = "0"
os.environ["NILS_CAP_CRM_PROSPECT_CREATE"] = "1"
os.environ["NILS_CAP_CRM_READ"] = "1"
os.environ["NILS_CAP_EMAIL_SEND"] = "0"
os.environ["NILS_CAP_N8N"] = "0"
os.environ["NILS_CRM_BACKEND"] = "sqlite"
STAGING_DB = (os.environ.get("NILS_CRM_DB") or "").strip()
assert STAGING_DB, "NILS_CRM_DB required"
assert "staging-entity" in STAGING_DB or "entity-routing" in STAGING_DB, STAGING_DB
# Forbid reusing the first canary DB
assert "20260802.db" not in STAGING_DB, "must use a NEW staging DB, not the first canary file"
os.environ["NILS_CRM_DB"] = STAGING_DB
os.environ.pop("NILS_CRM_DATABASE_URL", None)

from nils_job_runtime import control_plane, promise_guard, store  # noqa: E402
from nils_job_runtime import crm_offer_service as crm  # noqa: E402
from nils_job_runtime import turn_context as tc  # noqa: E402
from nils_job_runtime import turn_routing as tr  # noqa: E402
from nils_job_runtime.model import ACTIVE  # noqa: E402

RESULTS: list[dict] = []
TURNS: list[dict] = []


def tg_send(chat_id: str, text: str) -> None:
    try:
        import telegram_ops as tg

        tg.send_message(chat_id, text[:3500])
    except Exception as e:
        print("TG_SEND_FAIL", type(e).__name__, str(e)[:120])


def log_turn(label: str, user_text: str, res: dict) -> None:
    job = res.get("job") or {}
    turn = tc.load(job) if job else None
    collected = (turn or {}).get("collected_parameters") or {}
    entry = {
        "label": label,
        "release_id": RELEASE_ID,
        "commit_id": COMMIT_ID,
        "user_text": user_text,
        "bot_text": (res.get("text") or "")[:800],
        "ok": res.get("ok"),
        "route": res.get("route"),
        "chat_id": job.get("telegram_chat_id") or "",
        "message_id": job.get("telegram_message_id"),
        "job_id": job.get("job_id"),
        "status": job.get("status"),
        "current_intent": job.get("capability") or (turn or {}).get("intent") or "",
        "previous_intent": "",
        "current_entity": collected.get("company")
        or collected.get("contact")
        or tr.primary_entity(user_text),
        "previous_entity": "",
        "context_reused": bool(res.get("resumed")),
        "reuse_reason": "resume" if res.get("resumed") else "fresh_or_clarify",
        "selected_capability": job.get("capability") or "",
        "selected_tool": job.get("capability") or job.get("task_type") or "",
        "guard_result": res.get("blocked_reason") or res.get("route") or "",
        "final_action": res.get("route") or "",
        "database": STAGING_DB,
        "record_ids": {
            "company": collected.get("company"),
            "contact": collected.get("contact"),
            "company_id": None,
            "contact_id": None,
        },
    }
    TURNS.append(entry)
    print("===", label, "release=", RELEASE_ID, "commit=", COMMIT_ID[:12] if COMMIT_ID else "", "===")
    print("USER:", user_text)
    print("BOT:", (res.get("text") or "")[:500])
    print(
        "META",
        json.dumps(
            {
                k: entry[k]
                for k in (
                    "job_id",
                    "status",
                    "route",
                    "current_intent",
                    "current_entity",
                    "context_reused",
                    "guard_result",
                    "database",
                    "release_id",
                    "commit_id",
                )
            },
            ensure_ascii=False,
        ),
    )


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append({"name": name, "ok": bool(cond), "detail": (detail or "")[:400]})
    print(("PASS" if cond else "FAIL"), name, (detail or "")[:220])


def clear_active(chat: str) -> None:
    con = store.connect()
    try:
        rows = con.execute(
            f"SELECT job_id FROM nils_jobs WHERE telegram_chat_id=? AND status IN ({','.join('?' for _ in ACTIVE)})",
            (chat, *sorted(ACTIVE)),
        ).fetchall()
        for r in rows:
            try:
                store.transition(
                    r["job_id"],
                    "CANCELLED",
                    extra={
                        "finished_at": store.utc_now(),
                        "progress_message": "staging canary pre-clean",
                    },
                )
            except Exception:
                pass
    finally:
        con.close()


def company_count() -> int:
    con = crm._connect(readonly=True)
    try:
        return int(con.execute("SELECT COUNT(*) AS n FROM companies").fetchone()["n"])
    finally:
        con.close()


def find_company(name: str):
    con = crm._connect(readonly=True)
    try:
        return con.execute(
            "SELECT id, name, lifecycle_status, customer_number FROM companies WHERE name = ?",
            (name,),
        ).fetchone()
    finally:
        con.close()


def main() -> int:
    assert crm.crm_backend() == "sqlite"
    chat = (
        os.getenv("TELEGRAM_OWNER_CHAT_ID")
        or os.getenv("NILS_CONTROL_PLANE_ALLOWLIST")
        or ""
    ).split(",")[0].strip()
    assert chat, "no owner chat id"

    # Fresh DB only
    db_path = Path(STAGING_DB)
    if db_path.exists():
        db_path.unlink()
    crm.seed_isolated_fixture(db_path, reset=True)
    con = crm._connect(readonly=False)
    try:
        row = con.execute(
            "SELECT id FROM companies WHERE name = ?",
            ("Snack House Yassine",),
        ).fetchone()
        if not row:
            con.execute(
                """
                INSERT INTO companies (
                    tenant_id, name, customer_number, sales_lifecycle,
                    lifecycle_status, lead_source, status
                ) VALUES (1, 'Snack House Yassine', '', 'PROSPECT', 'PROSPECT', 'manual', 'neu')
                """
            )
            con.commit()
    finally:
        con.close()

    store.ensure_schema()
    clear_active(chat)
    mid = int(time.time()) % 1000000 + 90000

    tg_send(
        chat,
        "🧪 Nils FINAL Staging-Canary Entity-Routing\n"
        f"release={RELEASE_ID}\ncommit={COMMIT_ID[:12] if COMMIT_ID else '?'}\n"
        f"DB=NEW staging sqlite\nKeine Production-Writes. Kein Hotfix.",
    )

    def wh(text: str, label: str) -> dict:
        nonlocal mid
        mid += 1
        r = (
            control_plane.maybe_handle(
                text=text, chat_id=chat, user_id=chat, message_id=mid
            )
            or {}
        )
        log_turn(label, text, r)
        tg_send(
            chat,
            f"CANARY {label}\nrel={RELEASE_ID}\nDu: {text}\n\nNils: {(r.get('text') or '')[:900]}",
        )
        return r

    # --- A ---
    wh("Zeig mir das Angebot der mbp Service GmbH in Krefeld.", "A0_offer_mbp")
    r_a = wh("Lege Hassan Yassine als potentiellen Kunden an.", "A_create_hassan")
    ta = (r_a.get("text") or "").lower()
    check(
        "A_clarify_person_company",
        "hassan yassine" in ta
        and ("person" in ta or "ansprechpartner" in ta)
        and "unternehmen" in ta,
        (r_a.get("text") or "")[:240],
    )
    check(
        "A_no_mbp_leak",
        "mbp" not in ta
        and "krefeld" not in ta
        and "angebot" not in ta
        and "dokument" not in ta
        and "schau" not in ta
        and "moment" not in ta,
        (r_a.get("text") or "")[:240],
    )
    check(
        "A_not_offer_resume",
        (r_a.get("route") or "") != "control_crm_resume"
        and ((r_a.get("job") or {}).get("capability") == "crm.prospect_create"),
        f"route={r_a.get('route')} cap={(r_a.get('job') or {}).get('capability')}",
    )
    job_a = (r_a.get("job") or {}).get("job_id")

    # --- B ---
    r_b = wh("Als Ansprechpartner bei Snack House Yassine.", "B_ansprechpartner")
    tb = r_b.get("text") or ""
    check(
        "B_person_and_company",
        "Hassan Yassine" in tb and "Snack House Yassine" in tb,
        tb[:240],
    )
    check(
        "B_approval_or_prepared",
        (r_b.get("job") or {}).get("status") == "WAITING_FOR_APPROVAL"
        and ("vorbereitet" in tb.lower() or "freigabe" in tb.lower()),
        f"status={(r_b.get('job') or {}).get('status')} text={tb[:200]}",
    )
    r_b2 = wh("ja", "B_approve")
    tb2 = r_b2.get("text") or ""
    check(
        "B_created_prospect",
        (
            (r_b2.get("ok") is True)
            or (r_b2.get("job") or {}).get("status") in ("SUCCEEDED", "COMPLETED")
        )
        and (
            "Interessent angelegt" in tb2
            or "gibt es schon" in tb2.lower()
            or "schon im crm" in tb2.lower()
        ),
        tb2[:240],
    )
    shy = find_company("Snack House Yassine")
    shy_d = dict(shy) if shy else {}
    life = str(shy_d.get("lifecycle_status") or "")
    check("B_lifecycle_prospect", shy is not None and life.upper() == "PROSPECT", str(shy_d))
    check("B_no_invented_stammdaten", "@" not in tb2 and "telefon" not in tb2.lower(), tb2[:160])

    # --- C ---
    r_c = wh("Zeig mir das Angebot noch einmal.", "C_noch_einmal")
    tc_txt = (r_c.get("text") or "").lower()
    check(
        "C_no_silent_mbp",
        "mbp" not in tc_txt
        and (
            "welche" in tc_txt
            or "firma" in tc_txt
            or "kontakt" in tc_txt
            or (r_c.get("job") or {}).get("status") == "NEEDS_CLARIFICATION"
        ),
        (r_c.get("text") or "")[:240],
    )

    # --- D ---
    clear_active(chat)
    canary_name = "Testbetrieb Canary GmbH"
    before = company_count()
    r_d = wh("Lege Testbetrieb Canary GmbH als Interessenten an.", "D_create_canary")
    check(
        "D_asks_approval",
        (r_d.get("job") or {}).get("status") == "WAITING_FOR_APPROVAL"
        and canary_name in (r_d.get("text") or ""),
        (r_d.get("text") or "")[:200],
    )
    wh("ja", "D_approve")
    after = company_count()
    row = find_company(canary_name)
    check(
        "D_one_record_prospect",
        after == before + 1
        and row is not None
        and str(row["lifecycle_status"]) == "PROSPECT"
        and not (row["customer_number"] or "").strip(),
        f"before={before} after={after} row={dict(row) if row else None}",
    )

    # --- E ---
    r_e = wh("Lege Testbetrieb Canary GmbH als Interessenten an.", "E_duplicate")
    te = r_e.get("text") or ""
    if (r_e.get("job") or {}).get("status") == "WAITING_FOR_APPROVAL":
        r_e2 = wh("ja", "E_duplicate_approve")
        te = (r_e2.get("text") or "") + "\n" + te
    after_e = company_count()
    check(
        "E_no_second_company",
        after_e == after
        and (
            "gibt es schon" in te.lower()
            or "schon im crm" in te.lower()
            or "bereits" in te.lower()
        ),
        f"count={after_e} text={te[:240]}",
    )

    # --- F: Ansprechpartner ohne Firma ---
    clear_active(chat)
    r_f = wh("Lege Max Mustermann als Ansprechpartner an.", "F_max_ohne_firma")
    tf = (r_f.get("text") or "").lower()
    check(
        "F_asks_company",
        "unternehmen" in tf
        or "firma" in tf
        or "bei welchem" in tf
        or "zu welchem" in tf
        or "person" in tf,
        (r_f.get("text") or "")[:240],
    )
    check(
        "F_no_invented_company",
        "gmbh" not in tf or "mustermann" in tf,
        (r_f.get("text") or "")[:200],
    )

    # --- G: old incomplete create + new Firma Alpha ---
    clear_active(chat)
    r_g0 = wh("Lege Unvollstaendig Alt GmbH als Interessenten an.", "G0_incomplete")
    old_g = (r_g0.get("job") or {}).get("job_id")
    # leave in WAITING_FOR_APPROVAL without ja
    check(
        "G0_waiting",
        (r_g0.get("job") or {}).get("status") == "WAITING_FOR_APPROVAL",
        str((r_g0.get("job") or {}).get("status")),
    )
    r_g = wh("Lege Firma Alpha als Interessenten an.", "G_firma_alpha")
    new_g = (r_g.get("job") or {}).get("job_id")
    tg = r_g.get("text") or ""
    old_row = store.get_job(old_g) if old_g else None
    check(
        "G_new_job_alpha",
        "Firma Alpha" in tg
        and new_g
        and new_g != old_g
        and (old_row or {}).get("status") == "CANCELLED",
        f"old={old_g}/{(old_row or {}).get('status')} new={new_g} text={tg[:180]}",
    )
    # cancel alpha approval without writing
    if new_g:
        try:
            store.transition(
                new_g,
                "CANCELLED",
                extra={"finished_at": store.utc_now(), "progress_message": "canary G cleanup"},
            )
        except Exception:
            pass

    # --- H: unmapped CRM execution ---
    clear_active(chat)
    r_h = (
        control_plane.maybe_handle(
            text="xyzzy lege an ohne klaren namen",
            chat_id=chat,
            user_id=chat,
            message_id=mid + 80,
        )
        or {}
    )
    log_turn("H_unmapped", "xyzzy lege an ohne klaren namen", r_h)
    check(
        "H_block_no_companion",
        r_h.get("route")
        in (
            "control_crm_unmapped_block",
            "control_pipeline",
            "control_turn_guard",
            "control_tool_guard",
        )
        or "nicht sicher" in (r_h.get("text") or "").lower()
        or "noch nicht" in (r_h.get("text") or "").lower(),
        f"route={r_h.get('route')} text={(r_h.get('text') or '')[:160]}",
    )
    fake = "Ich schau jetzt im CRM nach und hol dir das Dokument."
    cleaned = promise_guard.sanitize_reply(fake, job=None)
    check(
        "H_promise_guard",
        cleaned == promise_guard.NO_ACCESS_TEXT
        or "keinen funktionsfähigen" in cleaned.lower(),
        cleaned[:120],
    )

    check(
        "safety_staging_db",
        "staging" in STAGING_DB and crm.crm_backend() == "sqlite",
        f"backend={crm.crm_backend()} db={STAGING_DB}",
    )
    check(
        "safety_email_n8n_off",
        os.environ.get("NILS_CAP_EMAIL_SEND") == "0"
        and os.environ.get("NILS_CAP_N8N") == "0",
        "",
    )
    check("safety_release_id", bool(RELEASE_ID), RELEASE_ID)
    check("safety_commit_id", bool(COMMIT_ID) and len(COMMIT_ID) >= 7, COMMIT_ID)

    failed = [x for x in RESULTS if not x["ok"]]
    report = {
        "verdict": "READY_FOR_LIMITED_PRODUCTION_CANDIDATE" if not failed else "NOT_READY",
        "release_id": RELEASE_ID,
        "commit_id": COMMIT_ID,
        "database": STAGING_DB,
        "chat_id_tail": chat[-4:] if len(chat) >= 4 else "***",
        "turns": TURNS,
        "checks": RESULTS,
        "canary_company": canary_name,
        "canary_company_id": int(row["id"]) if row else None,
        "job_a": job_a,
        "hotfix_during_canary": False,
        "stamp": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
    }
    out_path = Path("/root/app/data/nils-entity-routing-final-canary-report.json")
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("REPORT", out_path)
    print("SUMMARY passed", len(RESULTS) - len(failed), "failed", len(failed))
    for f in failed:
        print("FAIL", f["name"], f["detail"])
    tg_send(
        chat,
        "🧪 Final-Canary fertig: "
        + ("PASS" if not failed else "FAIL")
        + f"\n{len(RESULTS)-len(failed)}/{len(RESULTS)}"
        + f"\nrel={RELEASE_ID} commit={COMMIT_ID[:12] if COMMIT_ID else '?'}",
    )
    if failed:
        print("CANARY_FAIL")
        return 1
    print("CANARY_OK", report["verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

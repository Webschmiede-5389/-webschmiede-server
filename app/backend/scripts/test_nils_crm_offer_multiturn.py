# -*- coding: utf-8 -*-
"""Regression A–I + webhook-path E2E for CRM multi-turn offer read.

Uses isolated CRM sqlite fixture. No production writes.
Simulates the same control_plane.maybe_handle entry as telegram_ops webhook.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

TMP = tempfile.mkdtemp(prefix="nils-crm-mt-")
DB = Path(TMP) / "nils-runtime-test.db"
CRM_DB = Path(TMP) / "nils-crm-test.db"
os.environ["NILS_RUNTIME_DB"] = str(DB)
os.environ["NILS_CRM_DB"] = str(CRM_DB)
os.environ["NILS_CRM_TENANT_ID"] = "1"
os.environ["NILS_CONTROL_PLANE"] = "1"
os.environ["NILS_CONTROL_PLANE_STAGING"] = "1"
os.environ["NILS_JOB_NOTIFY"] = "0"
os.environ["NILS_CAP_CALENDAR"] = "0"
os.environ["NILS_CAP_EMAIL_SEND"] = "0"
os.environ["NILS_CAP_POSTING"] = "0"
os.environ["NILS_CAP_N8N"] = "0"
os.environ["NILS_CAP_CRM_READ"] = "1"

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from nils_job_runtime import control_plane, store  # noqa: E402
from nils_job_runtime import crm_offer_service as crm  # noqa: E402
from nils_job_runtime import turn_context as tc  # noqa: E402
from nils_job_runtime.model import LIVE_CLAIM_OK  # noqa: E402

CHAT = "crm-e2e-chat-001"
UID = "crm-e2e-user-001"
RESULTS: list[tuple[str, str, str]] = []
TRANSCRIPT: list[dict[str, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, "PASS" if cond else "FAIL", detail[:300]))
    print(("PASS" if cond else "FAIL"), name, detail[:200])


def webhook(text: str, *, chat_id: str = CHAT, mid: int = 0) -> dict:
    """Same entry as telegram_ops → control_plane.maybe_handle."""
    r = control_plane.maybe_handle(
        text=text,
        chat_id=chat_id,
        user_id=UID,
        message_id=mid or None,
    )
    TRANSCRIPT.append(
        {
            "user": text,
            "bot": (r or {}).get("text") or "(passthrough/None)",
            "route": (r or {}).get("route") or "none",
            "ok": str((r or {}).get("ok")),
            "job_status": ((r or {}).get("job") or {}).get("status") or "",
        }
    )
    return r or {}


def queued_count() -> int:
    con = store.connect()
    try:
        return int(
            con.execute("SELECT COUNT(*) FROM nils_jobs WHERE status='QUEUED'").fetchone()[0]
        )
    finally:
        con.close()


def active_job():
    return store.get_single_active_for_chat(CHAT)


def main() -> int:
    store.ensure_schema()
    crm.seed_isolated_fixture(CRM_DB, reset=True)
    mid = 5000

    # --- A: multi-turn MBP ---
    mid += 1
    r1 = webhook("Zeig mir das Angebot aus dem CRM.", mid=mid)
    check(
        "A1_fragt_firma",
        (
            "firma" in (r1.get("text") or "").lower()
            or "unternehmen" in (r1.get("text") or "").lower()
            or "kontakt" in (r1.get("text") or "").lower()
        )
        and "welcher kunde" not in (r1.get("text") or "").lower()
        and "welchen kunden" not in (r1.get("text") or "").lower()
        and (r1.get("job") or {}).get("status") == "NEEDS_CLARIFICATION",
        r1.get("text"),
    )
    j1 = r1.get("job") or {}
    turn1 = tc.load(j1)
    check(
        "A1_turn_context",
        bool(turn1)
        and turn1.get("intent") == tc.INTENT_CRM_GET_OFFER
        and (
            "company" in (turn1.get("missing_parameters") or [])
            or "customer" in (turn1.get("missing_parameters") or [])
        ),
        json.dumps(turn1 or {}, ensure_ascii=False)[:200],
    )
    check("A1_not_queued", queued_count() == 0 and j1.get("status") not in LIVE_CLAIM_OK, j1.get("status"))

    mid += 1
    r2 = webhook("MBP Service", mid=mid)
    txt2 = r2.get("text") or ""
    check(
        "A2_angebot_angezeigt",
        r2.get("ok") is True
        and "ANG-1000" in txt2
        and "MBP Service" in txt2
        and "Unternehmen:" in txt2
        and "Kunde:" not in txt2
        and "Positionen" in txt2
        and "Website Setup" in txt2
        and "1.490" in txt2.replace(" ", ""),
        txt2[:250],
    )
    check(
        "A2_keine_bestaetigung",
        "freigabe" not in txt2.lower()
        and "mach das" not in txt2.lower()
        and "aufgenommen" not in txt2.lower()
        and "welcher kunde" not in txt2.lower()
        and "für welchen kunden" not in txt2.lower(),
        txt2[:120],
    )
    j2 = r2.get("job") or {}
    check(
        "A2_job_terminal",
        j2.get("status") in ("SUCCEEDED", "COMPLETED"),
        j2.get("status"),
    )
    check("H_kontext_geschlossen", active_job() is None, str(active_job()))

    # --- B: one-shot with customer ---
    mid += 1
    r3 = webhook("Zeig mir das Angebot von MBP Service.", mid=mid)
    txt3 = r3.get("text") or ""
    check(
        "B_direkt",
        r3.get("ok") is True and "ANG-1000" in txt3 and "MBP Service" in txt3,
        txt3[:200],
    )

    # --- C: multiple offers ---
    mid += 1
    r4 = webhook("Zeig mir das Angebot von Alpha Reinigung.", mid=mid)
    txt4 = r4.get("text") or ""
    check(
        "C_auswahl",
        "mehrere angebote" in txt4.lower()
        and "ANG-2000" in txt4
        and "ANG-2001" in txt4
        and (r4.get("job") or {}).get("status") == "NEEDS_CLARIFICATION",
        txt4[:250],
    )
    mid += 1
    r4b = webhook("1", mid=mid)
    check(
        "C_wahl_ok",
        r4b.get("ok") is True and "ANG-2001" in (r4b.get("text") or ""),
        (r4b.get("text") or "")[:200],
    )

    # --- D: multiple similar customers ---
    mid += 1
    r5 = webhook("Zeig mir das Angebot aus dem CRM.", mid=mid)
    mid += 1
    r5b = webhook("MBP", mid=mid)
    txt5 = r5b.get("text") or ""
    check(
        "D_kundenauswahl",
        "mehrere unternehmen" in txt5.lower()
        and (r5b.get("job") or {}).get("status") == "NEEDS_CLARIFICATION",
        txt5[:250],
    )
    mid += 1
    r5c = webhook("1", mid=mid)
    # selection 1 could be any MBP* — should show offer or further choice
    check(
        "D_nach_wahl",
        bool(r5c.get("text"))
        and (
            r5c.get("ok") is True
            or "angebot" in (r5c.get("text") or "").lower()
            or "kunden" in (r5c.get("text") or "").lower()
        ),
        (r5c.get("text") or "")[:200],
    )
    # clean up if still active
    act = active_job()
    if act:
        try:
            store.transition(
                act["job_id"],
                "CANCELLED",
                extra={"finished_at": store.utc_now()},
            )
        except Exception:
            pass

    # --- E: not found ---
    mid += 1
    r6 = webhook("Zeig mir das Angebot von FirmaGibtEsNichtXYZ.", mid=mid)
    check(
        "E_nicht_gefunden",
        r6.get("ok") is False
        and "nicht" in (r6.get("text") or "").lower()
        and (r6.get("job") or {}).get("status") == "FAILED",
        (r6.get("text") or "")[:200],
    )

    # --- F: CRM unreachable ---
    bad = Path(TMP) / "missing-crm.db"
    os.environ["NILS_CRM_DB"] = str(bad)
    # clear module probe cache path via env only
    mid += 1
    r7 = webhook("Zeig mir das Angebot von MBP Service.", mid=mid)
    check(
        "F_crm_down",
        r7.get("ok") is False
        and (
            (r7.get("job") or {}).get("status") == "FAILED"
            or (r7.get("blocked_reason") in ("CONNECTION_FAILED", "NOT_CONFIGURED"))
            or "nicht erreichbar" in (r7.get("text") or "").lower()
            or "preflight" in (r7.get("text") or "").lower()
        ),
        f"status={(r7.get('job') or {}).get('status')} text={(r7.get('text') or '')[:160]}",
    )
    os.environ["NILS_CRM_DB"] = str(CRM_DB)

    # --- G: clarification does not leave QUEUED blocking ---
    mid += 1
    r8 = webhook("Zeig mir das Angebot aus dem CRM.", mid=mid)
    check(
        "G_needs_clarification_not_queued",
        (r8.get("job") or {}).get("status") == "NEEDS_CLARIFICATION" and queued_count() == 0,
        f"status={(r8.get('job') or {}).get('status')} queued={queued_count()}",
    )
    # New job in another chat must still work (not global queue block)
    mid += 1
    r8b = webhook(
        "Zeig mir das Angebot von MBP Service.",
        chat_id="crm-e2e-chat-other",
        mid=mid,
    )
    check(
        "G_other_chat_ok",
        r8b.get("ok") is True and "ANG-1000" in (r8b.get("text") or ""),
        (r8b.get("text") or "")[:160],
    )
    # Cancel waiting on main chat
    act = active_job()
    if act:
        store.transition(act["job_id"], "CANCELLED", extra={"finished_at": store.utc_now()})

    # --- I: MBP Service is not free chat when waiting ---
    mid += 1
    r9 = webhook("Zeig mir das Angebot aus dem CRM.", mid=mid)
    mid += 1
    r9b = webhook("MBP Service", mid=mid)
    check(
        "I_resume_not_passthrough",
        r9b.get("route") == "control_crm_resume"
        and r9b.get("ok") is True
        and "ANG-1000" in (r9b.get("text") or ""),
        f"route={r9b.get('route')} text={(r9b.get('text') or '')[:160]}",
    )
    check("H2_nach_erfolg_kein_active", active_job() is None, str(active_job()))

    # Summary
    failed = [x for x in RESULTS if x[1] == "FAIL"]
    print("\n=== SUMMARY ===")
    print(f"passed={len(RESULTS) - len(failed)} failed={len(failed)} total={len(RESULTS)}")
    for name, st, detail in RESULTS:
        if st == "FAIL":
            print("FAIL", name, detail)

    out_dir = Path(
        r"C:\Users\kumex\OneDrive\Desktop\Jarvis\audits\infrastructure-audit-2026-07-29"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = {
        "verdict": "GO" if not failed else "NO-GO",
        "results": [{"name": n, "status": s, "detail": d} for n, s, d in RESULTS],
        "transcript": TRANSCRIPT,
        "crm_db": str(CRM_DB),
        "runtime_db": str(DB),
    }
    art_path = out_dir / "nils-crm-offer-multiturn-e2e-2026-07-31.json"
    art_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    print("artifact", art_path)
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)

# -*- coding: utf-8 -*-
"""Tests: CRM offer read + PDF send + promise guard (isolated, no CRM write/n8n)."""
from __future__ import annotations

import os
import sys
import tempfile
import traceback
from pathlib import Path
from unittest import mock

TMP = tempfile.mkdtemp(prefix="nils-offer-pdf-")
DB = Path(TMP) / "nils-runtime.db"
CRM_DB = Path(TMP) / "nils-crm.db"
os.environ["NILS_RUNTIME_DB"] = str(DB)
os.environ["NILS_CRM_DB"] = str(CRM_DB)
os.environ["NILS_CRM_BACKEND"] = "sqlite"
os.environ["NILS_CRM_TENANT_ID"] = "1"
os.environ["NILS_CONTROL_PLANE"] = "1"
os.environ["NILS_CONTROL_PLANE_STAGING"] = "1"
os.environ["NILS_JOB_NOTIFY"] = "0"
os.environ["NILS_CAP_CALENDAR"] = "0"
os.environ["NILS_CAP_EMAIL_SEND"] = "0"
os.environ["NILS_CAP_POSTING"] = "0"
os.environ["NILS_CAP_N8N"] = "0"
os.environ["NILS_CAP_CRM_READ"] = "1"
os.environ["NILS_CAP_CRM_OFFER_PDF"] = "1"
os.environ["NILS_WORKER_LIVE_CAPABILITIES"] = "crm.offer_read,crm.offer_pdf_send"
os.environ.pop("NILS_CRM_DATABASE_URL", None)

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from nils_job_runtime import control_plane, promise_guard, queue, store, worker  # noqa: E402
from nils_job_runtime import crm_offer_service as crm  # noqa: E402
from nils_job_runtime import offer_pdf  # noqa: E402
from nils_job_runtime import turn_context as tc  # noqa: E402

CHAT = "pdf-e2e-chat"
UID = "pdf-e2e-user"
RESULTS: list[tuple[str, str, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, "PASS" if cond else "FAIL", detail[:300]))
    print(("PASS" if cond else "FAIL"), name, detail[:220])


def webhook(text: str, *, mid: int = 0) -> dict:
    return (
        control_plane.maybe_handle(
            text=text, chat_id=CHAT, user_id=UID, message_id=mid or None
        )
        or {}
    )


def main() -> int:
    store.ensure_schema()
    crm.seed_isolated_fixture(CRM_DB, reset=True)
    mid = 7000

    # --- Promise guard ---
    bad = promise_guard.sanitize_reply(
        "Ich sende dir gleich das PDF und lege den Kunden an.", job=None
    )
    check("guard_no_job", "noch nicht" in bad.lower() or "keinen funktionsfähigen" in bad.lower(), bad)

    # --- Capability disabled ---
    mid += 1
    r = webhook("Lege einen Kunden an für Testfirma", mid=mid)
    check(
        "write_blocked",
        promise_guard.CAPABILITY_DISABLED_TEXT in (r.get("text") or ""),
        r.get("text"),
    )

    mid += 1
    r = webhook("Erstelle ein Angebot für ProOffice", mid=mid)
    check(
        "offer_write_blocked",
        promise_guard.CAPABILITY_DISABLED_TEXT in (r.get("text") or ""),
        r.get("text"),
    )

    # --- ANG-0004 → Digitale Handwerkskunst ---
    mid += 1
    r = webhook("Zeig mir ANG-0004", mid=mid)
    txt = r.get("text") or ""
    check(
        "ang0004_dhk",
        r.get("ok") is True
        and "ANG-0004" in txt
        and "Digitale Handwerkskunst" in txt
        and "ProOffice" not in txt,
        txt[:200],
    )

    # --- ProOffice kein Angebot ---
    mid += 1
    r = webhook("Zeig mir das Angebot für ProOffice Leverkusen", mid=mid)
    txt = r.get("text") or ""
    check(
        "prooffice_no_offer",
        "kein angebot" in txt.lower()
        and "ProOffice" in txt
        and "ANG-0004" not in txt,
        txt[:200],
    )

    # --- PDF resolve + mock sendDocument ---
    sent: list[dict] = []

    def _fake_send_document(chat_id, path, *, filename=None, caption="", max_bytes=None):
        p = Path(path)
        sent.append(
            {
                "chat_id": str(chat_id),
                "path": str(path),
                "filename": filename,
                "exists": p.is_file(),
                "size": p.stat().st_size if p.is_file() else 0,
                "caption": caption,
            }
        )
        return {"ok": True, "result": {"message_id": 1}}

    mid += 1
    with mock.patch("telegram_ops.send_document", side_effect=_fake_send_document):
        r = webhook("Schick mir das Angebot als PDF für Digitale Handwerkskunst", mid=mid)
        check(
            "pdf_queued",
            (r.get("job") or {}).get("status") == "QUEUED"
            and (r.get("job") or {}).get("capability") == "crm.offer_pdf_send",
            f"status={(r.get('job') or {}).get('status')} shadow={(r.get('job') or {}).get('shadow')} cap={(r.get('job') or {}).get('capability')}",
        )
        jid = (r.get("job") or {}).get("job_id")
        job = queue.claim_next(
            shadow_only=True,
            live_capabilities={"crm.offer_pdf_send", "crm.offer_read"},
        )
        check("pdf_claimed", bool(job) and job.get("job_id") == jid, str(job and job.get("job_id")))
        if job:
            worker.run_job(job, wid="test-worker")
        final = store.get_job(jid) if jid else None
        check(
            "pdf_succeeded",
            final and final.get("status") in ("SUCCEEDED", "COMPLETED"),
            final and final.get("status"),
        )
        check(
            "pdf_sent_correct_file",
            len(sent) == 1
            and sent[0]["exists"]
            and "ANG-0004" in (sent[0]["filename"] or "")
            and "Digitale" in (sent[0]["filename"] or "")
            and sent[0]["chat_id"] == CHAT,
            str(sent),
        )
        # temp cleaned
        check("pdf_temp_removed", not Path(sent[0]["path"]).exists(), sent[0]["path"])

    # --- PDF send failure → FAILED ---
    mid += 1
    sent.clear()

    def _fail_send(*_a, **_k):
        return {"ok": False, "error": "simulated_tg_fail"}

    with mock.patch("telegram_ops.send_document", side_effect=_fail_send):
        r = webhook("Schick mir das Angebot als PDF für Digitale Handwerkskunst", mid=mid)
        jid = (r.get("job") or {}).get("job_id")
        job = queue.claim_next(
            shadow_only=True, live_capabilities={"crm.offer_pdf_send"}
        )
        if job:
            worker.run_job(job, wid="test-worker-2")
        final = store.get_job(jid) if jid else None
        check(
            "pdf_send_fail",
            final and final.get("status") == "FAILED",
            final and f"{final.get('status')}:{final.get('error_message_redacted')}",
        )

    # --- ProOffice PDF: no invent ---
    mid += 1
    r = webhook("Schick mir das Angebot als PDF für ProOffice Leverkusen", mid=mid)
    txt = r.get("text") or ""
    check(
        "prooffice_pdf_none",
        "kein angebot" in txt.lower() and "ANG-0004" not in txt,
        txt[:200],
    )

    # --- Ambiguity ---
    mid += 1
    r = webhook("Zeig mir das Angebot für MBP Service", mid=mid)
    # fixture has MBP Service exact + West/Ost — exact match should succeed for MBP Service alone
    # For ambiguous query "MBP":
    mid += 1
    r = webhook("Zeig mir das Angebot für MBP", mid=mid)
    check(
        "ambiguous_clarify",
        (r.get("job") or {}).get("status") == "NEEDS_CLARIFICATION"
        or "mehrere" in (r.get("text") or "").lower(),
        r.get("text"),
    )

    # --- Stop cancels PDF job ---
    mid += 1
    with mock.patch("telegram_ops.send_document", side_effect=_fake_send_document):
        r = webhook("Schick mir das Angebot als PDF für Digitale Handwerkskunst", mid=mid)
        jid = (r.get("job") or {}).get("job_id")
        mid += 1
        stop = webhook("Stop", mid=mid)
        final = store.get_job(jid) if jid else None
        check(
            "stop_cancels_pdf",
            final and final.get("status") in ("CANCELLED", "CANCEL_REQUESTED"),
            final and final.get("status"),
        )

    # --- Capability off ---
    os.environ["NILS_CAP_CRM_OFFER_PDF"] = "0"
    mid += 1
    r = webhook("Schick mir das Angebot als PDF für Digitale Handwerkskunst", mid=mid)
    check(
        "cap_off",
        promise_guard.CAPABILITY_DISABLED_TEXT in (r.get("text") or "")
        or "deaktiviert" in (r.get("text") or "").lower()
        or "nicht ausführen" in (r.get("text") or "").lower(),
        r.get("text"),
    )
    os.environ["NILS_CAP_CRM_OFFER_PDF"] = "1"

    # --- PDF render unit ---
    offers = crm.list_offers_by_number("ANG-0004")
    check("fixture_ang", bool(offers) and offers[0].company_name == "Digitale Handwerkskunst", str(offers[:1]))
    if offers:
        out = Path(TMP) / "t.pdf"
        offer_pdf.render_offer_pdf(offers[0], dest=out)
        check("pdf_bytes", out.is_file() and out.stat().st_size > 100 and out.read_bytes()[:4] == b"%PDF", str(out.stat().st_size if out.exists() else 0))

    # --- No CRM writes / flags ---
    check("nils_write_env_absent_or_false", os.getenv("NILS_WRITE_ENABLED", "false").lower() in ("0", "false", "no", "off", ""), "")
    check("n8n_cap_off", os.environ.get("NILS_CAP_N8N") == "0", "")

    failed = [x for x in RESULTS if x[1] == "FAIL"]
    print("\n=== SUMMARY ===")
    for n, s, d in RESULTS:
        print(f"{s}\t{n}\t{d[:80]}")
    print(f"TOTAL {len(RESULTS)} FAIL {len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)

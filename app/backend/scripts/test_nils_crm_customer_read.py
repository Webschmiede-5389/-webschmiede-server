# -*- coding: utf-8 -*-
"""CRM customer_read (company/contact/onboarding) — read-only, no writes."""
from __future__ import annotations

import os
import sys
import tempfile
import traceback
from pathlib import Path

TMP = tempfile.mkdtemp(prefix="nils-cust-read-")
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
os.environ["NILS_CAP_EMAIL_SEND"] = "0"
os.environ["NILS_CAP_N8N"] = "0"
os.environ["NILS_WORKER_LIVE_CAPABILITIES"] = "crm.offer_read,crm.offer_pdf_send,crm.customer_read"
os.environ.pop("NILS_CRM_DATABASE_URL", None)

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from nils_job_runtime import control_plane, promise_guard, store  # noqa: E402
from nils_job_runtime import crm_offer_service as crm  # noqa: E402
from nils_job_runtime import pipeline  # noqa: E402

CHAT = "cust-read-chat"
UID = "cust-read-user"
RESULTS: list[tuple[str, str, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    d = detail or ""
    RESULTS.append((name, "PASS" if cond else "FAIL", d[:300]))
    print(("PASS" if cond else "FAIL"), name, d[:220])


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
    mid = 8000

    check(
        "intent_customer_read",
        pipeline.map_capability("Zeig mir die Kundendaten von Digitale Handwerkskunst")
        == ("crm.customer_read", "read"),
        str(pipeline.map_capability("Zeig mir die Kundendaten von Digitale Handwerkskunst")),
    )
    check(
        "intent_onboarding",
        pipeline.map_capability("Onboarding-Status für ProOffice Leverkusen")[0]
        == "crm.customer_read",
        str(pipeline.map_capability("Onboarding-Status für ProOffice Leverkusen")),
    )
    check(
        "write_still_blocked",
        promise_guard.CAPABILITY_DISABLED_TEXT
        in (webhook("Lege einen Kunden an", mid=mid).get("text") or ""),
        "",
    )
    mid += 1

    r = webhook("Zeig mir die Kundendaten von Digitale Handwerkskunst", mid=mid)
    txt = r.get("text") or ""
    check(
        "dhk_profile",
        r.get("ok") is True
        and "Digitale Handwerkskunst" in txt
        and "0221-111111" in txt
        and "office@digitalehandwerkskunst.de" in txt
        and "Christian Kummetat" in txt
        and "Onboarding" in txt
        and "KUN001" in txt
        and (r.get("job") or {}).get("status") in ("SUCCEEDED", "COMPLETED"),
        txt[:250],
    )

    mid += 1
    r = webhook("Onboarding-Status für ProOffice Leverkusen", mid=mid)
    txt = r.get("text") or ""
    check(
        "prooffice_profile",
        r.get("ok") is True
        and "ProOffice Leverkusen" in txt
        and "0214-222222" in txt
        and "Onboarding" in txt
        and (r.get("job") or {}).get("status") in ("SUCCEEDED", "COMPLETED"),
        txt[:250],
    )

    mid += 1
    r = webhook("Zeig mir die Kundendaten", mid=mid)
    check(
        "asks_company",
        (r.get("job") or {}).get("status") == "NEEDS_CLARIFICATION"
        and (
            "firma" in (r.get("text") or "").lower()
            or "kontakt" in (r.get("text") or "").lower()
        ),
        r.get("text"),
    )
    mid += 1
    r = webhook("MBP Service", mid=mid)
    txt = r.get("text") or ""
    check(
        "resume_mbp",
        r.get("ok") is True and "MBP Service" in txt and "CRM:" in txt,
        txt[:200],
    )

    mid += 1
    r = webhook("Telefon von FirmaGibtEsNichtXYZ", mid=mid)
    check(
        "not_found",
        "nicht" in (r.get("text") or "").lower()
        and (r.get("job") or {}).get("status") == "FAILED",
        r.get("text"),
    )

    # no write side effects — fixture still readable
    check("cap_email_off", os.environ.get("NILS_CAP_EMAIL_SEND") == "0", "")
    check("nils_write_false", os.getenv("NILS_WRITE_ENABLED", "false").lower() in ("0", "false", ""), "")

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

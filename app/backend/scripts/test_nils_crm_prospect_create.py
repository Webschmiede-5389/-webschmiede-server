# -*- coding: utf-8 -*-
"""crm.prospect_create — PROSPECT only, approval required, customer_write still blocked."""
from __future__ import annotations

import os
import sys
import tempfile
import traceback
from pathlib import Path

TMP = tempfile.mkdtemp(prefix="nils-prospect-")
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
os.environ["NILS_PROSPECT_PILOT_STATE"] = str(Path(TMP) / "pilot-state.json")
os.environ["NILS_PROSPECT_PILOT_AUDIT_DIR"] = str(Path(TMP) / "pilot-audit")
os.environ["NILS_PROSPECT_PILOT_MAX"] = "5"
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

CHAT = "prospect-chat"
UID = "prospect-user"
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
    mid = 9200

    check(
        "intent_prospect",
        pipeline.map_capability("Leg Müller Dach GmbH mit Peter Müller an")
        == ("crm.prospect_create", "write"),
        str(pipeline.map_capability("Leg Müller Dach GmbH mit Peter Müller an")),
    )
    check(
        "extract_company",
        pipeline.extract_company_from_text("Leg Müller Dach GmbH mit Peter Müller an")
        == "Müller Dach GmbH",
        pipeline.extract_company_from_text("Leg Müller Dach GmbH mit Peter Müller an"),
    )
    check(
        "extract_contact",
        pipeline.extract_contact_from_text("Leg Müller Dach GmbH mit Peter Müller an")
        == "Peter Müller",
        pipeline.extract_contact_from_text("Leg Müller Dach GmbH mit Peter Müller an"),
    )
    check(
        "customer_write_still_blocked_intent",
        pipeline.map_capability("Lege einen Kunden an")[0] == "crm.customer_write",
        str(pipeline.map_capability("Lege einen Kunden an")),
    )

    r = webhook("Lege einen Kunden an", mid=mid)
    mid += 1
    check(
        "customer_write_blocked",
        promise_guard.CAPABILITY_DISABLED_TEXT in (r.get("text") or ""),
        r.get("text") or "",
    )

    r = webhook("Leg Müller Dach GmbH mit Peter Müller an", mid=mid)
    mid += 1
    check(
        "asks_approval",
        (r.get("job") or {}).get("status") == "WAITING_FOR_APPROVAL"
        and "ich würde folgenden interessenten" in (r.get("text") or "").lower()
        and "Müller Dach" in (r.get("text") or "")
        and "Peter Müller" in (r.get("text") or "")
        and "prospect" in (r.get("text") or "").lower(),
        f"status={(r.get('job') or {}).get('status')} text={(r.get('text') or '')[:200]}",
    )

    # counts before approve
    con = crm._connect(readonly=True)
    try:
        before = int(con.execute("SELECT COUNT(*) AS n FROM companies").fetchone()["n"])
    finally:
        con.close()

    r = webhook("ja", mid=mid)
    mid += 1
    txt = r.get("text") or ""
    check(
        "created_after_ja",
        r.get("ok") is True
        and "Interessent angelegt" in txt
        and "Müller Dach GmbH" in txt
        and "Peter Müller" in txt
        and "kein kunde" in txt.lower()
        and (r.get("job") or {}).get("status") in ("SUCCEEDED", "COMPLETED"),
        txt[:250],
    )

    con = crm._connect(readonly=True)
    try:
        after = int(con.execute("SELECT COUNT(*) AS n FROM companies").fetchone()["n"])
        row = con.execute(
            "SELECT lifecycle_status, customer_number FROM companies WHERE name = ?",
            ("Müller Dach GmbH",),
        ).fetchone()
        n_contacts = int(
            con.execute(
                "SELECT COUNT(*) AS n FROM contacts WHERE company_id = ("
                "SELECT id FROM companies WHERE name = 'Müller Dach GmbH' LIMIT 1)"
            ).fetchone()["n"]
        )
    finally:
        con.close()

    check("company_count_plus_one", after == before + 1, f"{before}->{after}")
    check(
        "lifecycle_prospect_no_number",
        row is not None
        and str(row["lifecycle_status"]) == "PROSPECT"
        and not (row["customer_number"] or "").strip(),
        str(dict(row) if row else None),
    )
    check("contact_created", n_contacts == 1, str(n_contacts))

    r = webhook("Leg Müller Dach GmbH mit Peter Müller an", mid=mid)
    mid += 1
    txt_dup = (r.get("text") or "").lower()
    if (r.get("job") or {}).get("status") == "WAITING_FOR_APPROVAL":
        r = webhook("ja", mid=mid)
        mid += 1
        txt_dup = (r.get("text") or "").lower()
    check(
        "duplicate_no_second",
        "bereits vorhanden" in txt_dup or "gibt es schon" in txt_dup,
        (r.get("text") or "")[:200],
    )

    os.environ["NILS_CAP_CRM_PROSPECT_CREATE"] = "0"
    # reload module flag
    from nils_job_runtime import crm_prospect_service as prosp

    prosp._PROSPECT = prosp._PROSPECT  # keep
    r = webhook("Leg Neue Firma Test GmbH mit Max an", mid=mid)
    check(
        "cap_off_blocks",
        promise_guard.CAPABILITY_DISABLED_TEXT in (r.get("text") or "")
        or "noch nicht" in (r.get("text") or "").lower(),
        r.get("text") or "",
    )

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

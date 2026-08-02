# -*- coding: utf-8 -*-
"""Limited-production read-only gates A–C (no real insert)."""
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

assert os.environ.get("NILS_CRM_BACKEND", "").lower() == "postgres"
assert os.environ.get("NILS_CAP_CRM_PROSPECT_CREATE") == "1"
assert os.environ.get("NILS_CAP_EMAIL_SEND") == "0"
assert os.environ.get("NILS_CAP_N8N") == "0"

from nils_job_runtime import control_plane, store  # noqa: E402
from nils_job_runtime import crm_offer_service as crm  # noqa: E402
from nils_job_runtime import crm_prospect_pilot as pilot  # noqa: E402
from nils_job_runtime import turn_context as tc  # noqa: E402

RESULTS = []
NAME = "Beispiel Sicherheitsprüfung GmbH"


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append({"name": name, "ok": bool(cond), "detail": (detail or "")[:300]})
    print(("PASS" if cond else "FAIL"), name, (detail or "")[:200])


def count_named() -> int:
    con = crm._connect(readonly=True)
    try:
        row = con.execute(
            "SELECT COUNT(*) AS n FROM companies WHERE tenant_id = ? AND lower(name) = lower(?)",
            (crm.tenant_id(), NAME),
        ).fetchone()
        return int(row["n"] if row else 0)
    finally:
        con.close()


def company_total() -> int:
    con = crm._connect(readonly=True)
    try:
        row = con.execute(
            "SELECT COUNT(*) AS n FROM companies WHERE tenant_id = ?",
            (crm.tenant_id(),),
        ).fetchone()
        return int(row["n"] if row else 0)
    finally:
        con.close()


def main() -> int:
    chat = (
        os.getenv("TELEGRAM_OWNER_CHAT_ID")
        or os.getenv("NILS_CONTROL_PLANE_ALLOWLIST")
        or ""
    ).split(",")[0].strip()
    assert chat
    allow = (os.getenv("NILS_CONTROL_PLANE_ALLOWLIST") or "").strip()
    check("allowlist_owner_only", allow == chat, allow[-4:] if allow else "")
    check("tenant_1", str(crm.tenant_id()) == "1", str(crm.tenant_id()))
    check("backend_postgres", crm.crm_backend() == "postgres", crm.crm_backend())

    store.ensure_schema()
    # cancel any active
    active = store.get_single_active_for_chat(chat)
    if active:
        try:
            store.transition(
                active["job_id"],
                "CANCELLED",
                extra={"finished_at": store.utc_now(), "progress_message": "pilot pre-clean"},
            )
        except Exception:
            pass

    mid = int(time.time()) % 100000 + 50000
    before_named = count_named()
    before_total = company_total()

    # A preview only
    r_a = (
        control_plane.maybe_handle(
            text=f"Lege {NAME} als Interessenten an.",
            chat_id=chat,
            user_id=chat,
            message_id=mid,
        )
        or {}
    )
    ta = r_a.get("text") or ""
    check(
        "A_preview",
        (r_a.get("job") or {}).get("status") == "WAITING_FOR_APPROVAL"
        and "ich würde folgenden interessenten" in ta.lower()
        and NAME in ta
        and "prospect" in ta.lower(),
        ta[:220],
    )
    check("A_no_insert", count_named() == before_named and company_total() == before_total, "")
    job_a = (r_a.get("job") or {}).get("job_id")

    # B Abbrechen
    r_b = (
        control_plane.maybe_handle(
            text="Abbrechen.",
            chat_id=chat,
            user_id=chat,
            message_id=mid + 1,
        )
        or {}
    )
    job_b = store.get_job(job_a) if job_a else None
    check(
        "B_cancelled",
        (job_b or {}).get("status") == "CANCELLED"
        or (r_b.get("route") == "control_stop"),
        f"status={(job_b or {}).get('status')} route={r_b.get('route')}",
    )
    check("B_no_insert", count_named() == before_named, "")

    # C preview then expire without confirm
    r_c = (
        control_plane.maybe_handle(
            text=f"Lege {NAME} als Interessenten an.",
            chat_id=chat,
            user_id=chat,
            message_id=mid + 2,
        )
        or {}
    )
    job_c = r_c.get("job") or {}
    jid_c = job_c.get("job_id")
    check(
        "C_preview",
        job_c.get("status") == "WAITING_FOR_APPROVAL",
        str(job_c.get("status")),
    )
    # Fast-forward binding expiry (code path for 10 min TTL)
    turn = tc.load(job_c) if jid_c else None
    if turn:
        collected = dict(turn.get("collected_parameters") or {})
        binding = dict(collected.get("pilot_binding") or {})
        binding["expires_at"] = time.time() - 5
        collected["pilot_binding"] = binding
        turn["collected_parameters"] = collected
        tc.save(jid_c, turn)
    r_exp = (
        control_plane.maybe_handle(
            text="Ja",
            chat_id=chat,
            user_id=chat,
            message_id=mid + 3,
        )
        or {}
    )
    tex = (r_exp.get("text") or "").lower()
    check(
        "C_expired_no_write",
        "abgelaufen" in tex and count_named() == before_named,
        (r_exp.get("text") or "")[:200],
    )
    # cleanup
    if jid_c:
        try:
            j = store.get_job(jid_c)
            if j and j.get("status") not in ("CANCELLED", "SUCCEEDED", "FAILED"):
                store.transition(
                    jid_c,
                    "CANCELLED",
                    extra={"finished_at": store.utc_now(), "progress_message": "pilot C cleanup"},
                )
        except Exception:
            pass

    check("C_final_no_insert", count_named() == before_named and company_total() == before_total, "")
    check("mail_cap_off", os.environ.get("NILS_CAP_EMAIL_SEND") == "0", "")
    check("n8n_cap_off", os.environ.get("NILS_CAP_N8N") == "0", "")

    failed = [x for x in RESULTS if not x["ok"]]
    report = {
        "verdict": "READONLY_GATES_PASS" if not failed else "READONLY_GATES_FAIL",
        "release_id": os.getenv("NILS_RELEASE_ID"),
        "commit": os.getenv("NILS_GIT_COMMIT"),
        "tenant_id": crm.tenant_id(),
        "checks": RESULTS,
        "before_total": before_total,
        "after_total": company_total(),
        "stamp": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "pilot_success_count": pilot.success_count(),
    }
    out = Path("/root/app/data/nils-prospect-pilot-readonly-report.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("REPORT", out)
    print("SUMMARY", len(RESULTS) - len(failed), "/", len(RESULTS), report["verdict"])
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""Staging tests A–J: prospect defaults country/legal_basis/outbound."""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

TMP = tempfile.mkdtemp(prefix="nils-prospect-defaults-")
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
os.environ["NILS_CAP_CRM_PROSPECT_CREATE"] = "1"
os.environ["NILS_CAP_EMAIL_SEND"] = "0"
os.environ["NILS_CAP_N8N"] = "0"
os.environ["NILS_CAP_CRM_DEAL_WRITE"] = "0"
os.environ["NILS_CAP_CRM_OFFER_WRITE"] = "0"
os.environ["NILS_CAP_CALENDAR"] = "0"
os.environ["NILS_WRITE_ENABLED"] = "0"
os.environ["NILS_PROSPECT_PILOT_STATE"] = str(Path(TMP) / "pilot-state.json")
os.environ["NILS_PROSPECT_PILOT_AUDIT_DIR"] = str(Path(TMP) / "pilot-audit")
os.environ["NILS_PROSPECT_PILOT_MAX"] = "5"
os.environ.pop("NILS_CRM_DATABASE_URL", None)

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from nils_job_runtime import control_plane, store  # noqa: E402
from nils_job_runtime import crm_offer_service as crm  # noqa: E402
from nils_job_runtime import crm_prospect_pilot as pilot  # noqa: E402
from nils_job_runtime import crm_prospect_service as prosp  # noqa: E402
from nils_job_runtime import turn_context as tc  # noqa: E402

CHAT = "defaults-chat"
UID = "defaults-user"
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), (detail or "")[:300]))
    print(("PASS" if cond else "FAIL"), name, (detail or "")[:200])


def wh(text: str, mid: int) -> dict:
    return (
        control_plane.maybe_handle(
            text=text, chat_id=CHAT, user_id=UID, message_id=mid
        )
        or {}
    )


def fetch_company(name: str):
    con = crm._connect(readonly=True)
    try:
        return con.execute(
            "SELECT id, name, lifecycle_status, customer_number, country, legal_basis, "
            "do_not_contact FROM companies WHERE lower(name)=lower(?)",
            (name,),
        ).fetchone()
    finally:
        con.close()


def main() -> int:
    store.ensure_schema()
    crm.seed_isolated_fixture(CRM_DB, reset=True)
    # force reload of prospect impl
    prosp._PROSPECT = None
    mid = 7000

    # A — name only
    r = wh("Lege Musterbetrieb GmbH als Interessenten an.", mid)
    mid += 1
    ta = r.get("text") or ""
    check(
        "A_preview_fields",
        "Musterbetrieb GmbH" in ta
        and "Land: nicht angegeben" in ta
        and "noch nicht bewertet" in ta
        and "Outbound: nicht freigegeben" in ta
        and "Lifecycle: PROSPECT" in ta,
        ta[:260],
    )
    r = wh("Ja", mid)
    mid += 1
    row = fetch_company("Musterbetrieb GmbH")
    check("A_created", row is not None, str(dict(row) if row else None))
    check(
        "A_null_defaults",
        row is not None
        and row["country"] is None
        and row["legal_basis"] is None
        and int(row["do_not_contact"] or 0) == 1
        and str(row["lifecycle_status"]) == "PROSPECT"
        and not (row["customer_number"] or "").strip(),
        str(dict(row) if row else None),
    )

    # B — country Deutschland (Land getrennt vom Firmennamen)
    r = wh(
        "Lege Landtest GmbH als Interessenten an. Standort Deutschland.",
        mid,
    )
    mid += 1
    tb = r.get("text") or ""
    check("B_preview_de", "Land: DE" in tb and "Landtest GmbH" in tb, tb[:200])
    r = wh("Anlegen", mid)
    mid += 1
    rowb = fetch_company("Landtest GmbH")
    check(
        "B_stored_de",
        rowb is not None and str(rowb["country"] or "") == "DE",
        str(dict(rowb) if rowb else None),
    )

    # C — no legal basis (already in A); outbound blocked helper
    check(
        "C_outbound_blocked",
        prosp.outbound_is_blocked(int(row["id"])) is True,
        "",
    )

    # D — explicit legal basis path (validated phrase)
    r = wh(
        "Lege Rechtsfirma GmbH als Interessenten an. "
        "Rechtsgrundlage: berechtigtes Interesse.",
        mid,
    )
    mid += 1
    td = r.get("text") or ""
    check(
        "D_preview_legal",
        "Rechtsfirma GmbH" in td
        and (
            "berechtigtes Interesse" in td
            or "lit. f" in td.lower()
            or "art. 6" in td.lower()
        ),
        td[:220],
    )
    r = wh("Bestätigen", mid)
    mid += 1
    rowd = fetch_company("Rechtsfirma GmbH")
    check(
        "D_stored_legal",
        rowd is not None and str(rowd["legal_basis"] or "") == "art6_1_f",
        str(dict(rowd) if rowd else None),
    )

    # E — duplicate
    r = wh("Lege Musterbetrieb GmbH als Interessenten an.", mid)
    mid += 1
    te = (r.get("text") or "").lower()
    check(
        "E_duplicate_blocked",
        "bereits vorhanden" in te or "gibt es schon" in te,
        (r.get("text") or "")[:200],
    )

    # F — expired preview
    r = wh("Lege Ablauf GmbH als Interessenten an.", mid)
    mid += 1
    job = r.get("job") or {}
    jid = job.get("job_id")
    turn = tc.load(job) if jid else None
    if turn:
        collected = dict(turn.get("collected_parameters") or {})
        binding = dict(collected.get("pilot_binding") or {})
        binding["expires_at"] = time.time() - 10
        collected["pilot_binding"] = binding
        turn["collected_parameters"] = collected
        tc.save(jid, turn)
    before = int(
        crm._connect(readonly=True)
        .execute("SELECT COUNT(*) AS n FROM companies")
        .fetchone()["n"]
    )
    r = wh("Ja", mid)
    mid += 1
    after = int(
        crm._connect(readonly=True)
        .execute("SELECT COUNT(*) AS n FROM companies")
        .fetchone()["n"]
    )
    check(
        "F_expired_no_write",
        "abgelaufen" in (r.get("text") or "").lower() and after == before,
        (r.get("text") or "")[:160],
    )

    # G — wrong owner (binding mismatch)
    r = wh("Lege Fremdowner GmbH als Interessenten an.", mid)
    mid += 1
    job = r.get("job") or {}
    jid = job.get("job_id")
    turn = tc.load(job) if jid else None
    if turn:
        collected = dict(turn.get("collected_parameters") or {})
        binding = dict(collected.get("pilot_binding") or {})
        binding["owner_id"] = "not-the-owner"
        collected["pilot_binding"] = binding
        turn["collected_parameters"] = collected
        tc.save(jid, turn)
    before = int(
        crm._connect(readonly=True)
        .execute("SELECT COUNT(*) AS n FROM companies WHERE lower(name)=lower(?)", ("Fremdowner GmbH",))
        .fetchone()["n"]
    )
    # confirm from correct chat but binding owner mismatch
    r = (
        control_plane.maybe_handle(
            text="Ja", chat_id=CHAT, user_id=UID, message_id=mid
        )
        or {}
    )
    mid += 1
    after = int(
        crm._connect(readonly=True)
        .execute("SELECT COUNT(*) AS n FROM companies WHERE lower(name)=lower(?)", ("Fremdowner GmbH",))
        .fetchone()["n"]
    )
    check(
        "G_wrong_owner_no_write",
        after == before,
        (r.get("text") or "")[:180],
    )

    # H — manipulated hash
    r = wh("Lege Hashfirma GmbH als Interessenten an.", mid)
    mid += 1
    job = r.get("job") or {}
    jid = job.get("job_id")
    turn = tc.load(job) if jid else None
    if turn:
        collected = dict(turn.get("collected_parameters") or {})
        binding = dict(collected.get("pilot_binding") or {})
        binding["payload_hash"] = "0" * 64
        collected["pilot_binding"] = binding
        turn["collected_parameters"] = collected
        tc.save(jid, turn)
    before = int(
        crm._connect(readonly=True)
        .execute("SELECT COUNT(*) AS n FROM companies WHERE lower(name)=lower(?)", ("Hashfirma GmbH",))
        .fetchone()["n"]
    )
    r = wh("Ja", mid)
    mid += 1
    after = int(
        crm._connect(readonly=True)
        .execute("SELECT COUNT(*) AS n FROM companies WHERE lower(name)=lower(?)", ("Hashfirma GmbH",))
        .fetchone()["n"]
    )
    check("H_hash_no_write", after == before, (r.get("text") or "")[:160])

    # I — other caps remain off in env
    check("I_email_off", os.environ.get("NILS_CAP_EMAIL_SEND") == "0", "")
    check("I_n8n_off", os.environ.get("NILS_CAP_N8N") == "0", "")
    check("I_deal_off", os.environ.get("NILS_CAP_CRM_DEAL_WRITE") == "0", "")
    check("I_offer_off", os.environ.get("NILS_CAP_CRM_OFFER_WRITE") == "0", "")
    check("I_calendar_off", os.environ.get("NILS_CAP_CALENDAR") == "0", "")
    check("I_write_enabled_off", os.environ.get("NILS_WRITE_ENABLED") == "0", "")

    # J — regression happy path still green
    r = wh("Leg Müller Dach GmbH mit Peter Müller an", mid)
    mid += 1
    check(
        "J_preview",
        (r.get("job") or {}).get("status") == "WAITING_FOR_APPROVAL"
        and "Müller Dach" in (r.get("text") or ""),
        (r.get("text") or "")[:160],
    )
    r = wh("Ja, anlegen", mid)
    mid += 1
    check(
        "J_created",
        "Interessent angelegt" in (r.get("text") or "")
        and "Outbound: nicht freigegeben" in (r.get("text") or ""),
        (r.get("text") or "")[:220],
    )

    # unit extractors
    check("extract_country_de", pilot.extract_country_from_text("Firma in Deutschland") == "DE")
    check("extract_country_none", pilot.extract_country_from_text("Firma Alpha") == "")
    check(
        "extract_legal_none",
        pilot.extract_legal_basis_from_text("Lege Firma an") == "",
    )
    check(
        "extract_legal_f",
        pilot.extract_legal_basis_from_text(
            "Lege X an. Rechtsgrundlage berechtigtes Interesse"
        )
        == "art6_1_f",
    )

    failed = [x for x in RESULTS if not x[1]]
    print("SUMMARY", len(RESULTS) - len(failed), "/", len(RESULTS))
    for n, ok, d in failed:
        print("FAIL", n, d)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

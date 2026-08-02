# -*- coding: utf-8 -*-
"""Isolated staging drill for prospect defaults patch (sqlite, no prod writes)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

TMP = tempfile.mkdtemp(prefix="nils-prospect-staging-drill-")
DB = Path(TMP) / "runtime.db"
CRM_DB = Path(TMP) / "crm.db"
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
os.environ["NILS_WRITE_ENABLED"] = "0"
os.environ["NILS_PROSPECT_PILOT_STATE"] = str(Path(TMP) / "pilot.json")
os.environ["NILS_PROSPECT_PILOT_AUDIT_DIR"] = str(Path(TMP) / "audit")
os.environ["NILS_PROSPECT_PILOT_MAX"] = "5"
os.environ.pop("NILS_CRM_DATABASE_URL", None)

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from nils_job_runtime import control_plane, store  # noqa: E402
from nils_job_runtime import crm_offer_service as crm  # noqa: E402
from nils_job_runtime import crm_prospect_service as prosp  # noqa: E402

NAME = "Staging Drill Defaults GmbH"
CHAT = "staging-drill"
CHECKS = []


def check(n, ok, d=""):
    CHECKS.append({"name": n, "ok": bool(ok), "detail": (d or "")[:240]})
    print(("PASS" if ok else "FAIL"), n, (d or "")[:180])


def main() -> int:
    store.ensure_schema()
    crm.seed_isolated_fixture(CRM_DB, reset=True)
    prosp._PROSPECT = None
    mid = 1
    r1 = control_plane.maybe_handle(
        text=f"Lege {NAME} als Interessenten an.",
        chat_id=CHAT,
        user_id=CHAT,
        message_id=mid,
    ) or {}
    t1 = r1.get("text") or ""
    check(
        "preview",
        "Land: nicht angegeben" in t1
        and "noch nicht bewertet" in t1
        and "Outbound: nicht freigegeben" in t1
        and NAME in t1,
        t1[:200],
    )
    mid += 1
    r2 = control_plane.maybe_handle(
        text="Ja", chat_id=CHAT, user_id=CHAT, message_id=mid
    ) or {}
    con = crm._connect(readonly=True)
    row = con.execute(
        "SELECT * FROM companies WHERE name=?", (NAME,)
    ).fetchone()
    n = int(con.execute("SELECT COUNT(*) AS n FROM companies WHERE name=?", (NAME,)).fetchone()["n"])
    con.close()
    check("created_once", n == 1 and row is not None, str(n))
    check(
        "db_values",
        row is not None
        and row["country"] is None
        and row["legal_basis"] is None
        and int(row["do_not_contact"] or 0) == 1
        and str(row["lifecycle_status"]) == "PROSPECT"
        and not (row["customer_number"] or "").strip(),
        str(dict(row) if row else None),
    )
    check("outbound_blocked", prosp.outbound_is_blocked(int(row["id"])), "")
    mid += 1
    r3 = control_plane.maybe_handle(
        text=f"Lege {NAME} als Interessenten an.",
        chat_id=CHAT,
        user_id=CHAT,
        message_id=mid,
    ) or {}
    check(
        "duplicate",
        "bereits vorhanden" in (r3.get("text") or "").lower(),
        (r3.get("text") or "")[:160],
    )
    # backup/restore of staging sqlite
    bak = Path(TMP) / "crm-backup.db"
    bak.write_bytes(CRM_DB.read_bytes())
    import sqlite3

    rcon = sqlite3.connect(str(bak))
    rcon.row_factory = sqlite3.Row
    rr = rcon.execute("SELECT country, legal_basis, lifecycle_status, customer_number FROM companies WHERE name=?", (NAME,)).fetchone()
    rcon.close()
    check(
        "backup_restore_row",
        rr is not None
        and rr["country"] is None
        and rr["legal_basis"] is None
        and rr["lifecycle_status"] == "PROSPECT"
        and not (rr["customer_number"] or "").strip(),
        str(dict(rr) if rr else None),
    )
    failed = [c for c in CHECKS if not c["ok"]]
    report = {
        "verdict": "STAGING_DRILL_PASS" if not failed else "STAGING_DRILL_FAIL",
        "checks": CHECKS,
        "stamp": datetime.now(timezone.utc).isoformat(),
    }
    print("VERDICT", report["verdict"], f"{len(CHECKS)-len(failed)}/{len(CHECKS)}")
    out = Path(
        r"C:\Users\kumex\OneDrive\Desktop\Jarvis\audits\infrastructure-audit-2026-07-29"
    ) / "nils-prospect-defaults-staging-drill-2026-08-02.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SAVED", out)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

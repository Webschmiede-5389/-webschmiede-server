# -*- coding: utf-8 -*-
"""Pilot binding / TTL / confirm phrases for crm.prospect_create."""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

TMP = tempfile.mkdtemp(prefix="nils-pilot-")
os.environ["NILS_PROSPECT_PILOT_STATE"] = str(Path(TMP) / "state.json")
os.environ["NILS_PROSPECT_PILOT_AUDIT_DIR"] = str(Path(TMP) / "audit")
os.environ["NILS_PROSPECT_CONFIRM_TTL_SEC"] = "600"
os.environ["NILS_PROSPECT_PILOT_MAX"] = "5"

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from nils_job_runtime import crm_prospect_pilot as pilot  # noqa: E402

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, cond, detail))
    print(("PASS" if cond else "FAIL"), name, detail[:160])


def main() -> int:
    check("confirm_ja", pilot.is_confirm_text("Ja"))
    check("confirm_anlegen", pilot.is_confirm_text("Anlegen"))
    check("confirm_bestaetigen", pilot.is_confirm_text("Bestätigen"))
    check("confirm_ja_anlegen", pilot.is_confirm_text("Ja, anlegen"))
    check("reject_ok", not pilot.is_confirm_text("ok"))
    check("reject_freigabe_ja", not pilot.is_confirm_text("freigabe ja"))

    payload = pilot.payload_dict(company="Alpha GmbH", contact="Max")
    turn = {"collected_parameters": dict(payload)}
    turn["collected_parameters"]["company"] = payload["company"]
    turn["collected_parameters"]["contact"] = payload["contact"]
    b = pilot.bind_preview(
        turn, chat_id="1", owner_id="1", job_id="J1", payload=payload
    )
    ok, reason, _ = pilot.validate_confirmation(
        turn, chat_id="1", owner_id="1", job_id="J1", text="Ja"
    )
    check("bind_ok", ok and reason == "ok", reason)

    turn2 = {"collected_parameters": dict(turn["collected_parameters"])}
    turn2["collected_parameters"]["pilot_binding"] = dict(b)
    turn2["collected_parameters"]["pilot_binding"]["expires_at"] = time.time() - 1
    ok2, reason2, _ = pilot.validate_confirmation(
        turn2, chat_id="1", owner_id="1", job_id="J1", text="Ja"
    )
    check("expired", (not ok2) and reason2 == "confirmation_expired", reason2)

    turn3 = {"collected_parameters": dict(turn["collected_parameters"])}
    turn3["collected_parameters"]["company"] = "Andere Firma"
    ok3, reason3, _ = pilot.validate_confirmation(
        turn3, chat_id="1", owner_id="1", job_id="J1", text="Ja"
    )
    check("payload_changed", (not ok3) and reason3 == "payload_changed", reason3)

    preview = pilot.format_preview(payload)
    check("preview_wording", "Ich würde folgenden Interessenten anlegen:" in preview)

    failed = [x for x in RESULTS if not x[1]]
    print("SUMMARY", len(RESULTS) - len(failed), "/", len(RESULTS))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

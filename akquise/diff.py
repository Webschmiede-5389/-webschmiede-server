"""Re-Scan Diff · Trigger wenn sich Lead-Daten ändern."""
from __future__ import annotations

import json
from pathlib import Path

AKQUISE_DIR = Path(__file__).resolve().parent
REPORT_DIR = AKQUISE_DIR.parent / "docs" / "akquise" / "reports"


def _lead_key(lead: dict) -> str:
    return f"{lead.get('name','').lower()}|{round(float(lead.get('lat') or 0), 4)}|{round(float(lead.get('lon') or 0), 4)}"


def find_previous_report(vertical: str) -> Path | None:
    files = sorted(
        REPORT_DIR.glob(f"*-{vertical}.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None


def diff_leads(old_leads: list[dict], new_leads: list[dict]) -> dict[str, dict]:
    old_map = {_lead_key(l): l for l in old_leads}
    changes: dict[str, dict] = {}

    for lead in new_leads:
        key = _lead_key(lead)
        prev = old_map.get(key)
        if not prev:
            changes[key] = {"type": "new", "triggers": ["Neuer Betrieb im Radius"], "lead": lead.get("name")}
            continue

        triggers: list[str] = []
        old_sig = prev.get("signals") or {}
        new_sig = lead.get("signals") or {}
        old_gp = prev.get("google_places") or {}
        new_gp = lead.get("google_places") or {}

        old_mgr = old_sig.get("contact_person") or ""
        new_mgr = new_sig.get("contact_person") or ""
        if new_mgr and old_mgr and new_mgr != old_mgr:
            triggers.append(f"Inhaber/GF geändert: {old_mgr} → {new_mgr}")

        old_rev = int(old_gp.get("user_ratings_total") or 0)
        new_rev = int(new_gp.get("user_ratings_total") or 0)
        if new_rev - old_rev >= 10:
            triggers.append(f"Google +{new_rev - old_rev} Bewertungen")

        if not old_sig.get("runs_facebook_ads") and new_sig.get("runs_facebook_ads"):
            triggers.append("Meta-Werbung neu, Marketing-Budget da")

        if not old_sig.get("order_signals") and new_sig.get("order_signals"):
            triggers.append("Online-Bestellen/Termin neu sichtbar")

        if not prev.get("website") and lead.get("website"):
            triggers.append("Website neu online")

        if triggers:
            changes[key] = {"type": "changed", "triggers": triggers, "lead": lead.get("name")}

    return changes


def apply_diff_to_report(report: dict) -> dict:
    prev_path = find_previous_report(report.get("vertical", "gastro"))
    if not prev_path:
        report["diff"] = {"previous": None, "changes": 0, "trigger_count": 0}
        return report

    try:
        old = json.loads(prev_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        report["diff"] = {"previous": prev_path.name, "changes": 0, "trigger_count": 0}
        return report

    # Gleicher Lauf überschreibt, nur diff wenn alter Report andere generated_at
    if old.get("generated_at") == report.get("generated_at"):
        report["diff"] = {"previous": prev_path.name, "changes": 0, "trigger_count": 0}
        return report

    changes = diff_leads(old.get("leads") or [], report.get("leads") or [])
    trigger_names: list[str] = []
    for key, ch in changes.items():
        for lead in report["leads"]:
            if _lead_key(lead) == key:
                lead["triggers"] = ch.get("triggers", [])
                lead["trigger_type"] = ch.get("type")
                if ch.get("triggers"):
                    trigger_names.append(lead.get("name", ""))
                break

    report["diff"] = {
        "previous": prev_path.name,
        "changes": len(changes),
        "trigger_count": len(trigger_names),
        "trigger_leads": trigger_names[:25],
    }
    return report

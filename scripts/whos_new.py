#!/usr/bin/env python3
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

vertical = sys.argv[1] if len(sys.argv) > 1 else "gastro"
use_server = "--server" in sys.argv

if use_server:
    import paramiko
    from agency_config import ssh_connect
    c = paramiko.SSHClient()
    ssh_connect(c)
    s = c.open_sftp()
    tmp = Path(tempfile.mktemp(suffix=".json"))
    s.get(f"/root/app/docs/akquise/reports/2026-07-15-{vertical}.json", str(tmp))
    s.close()
    c.close()
    path = tmp
else:
    files = sorted((ROOT / "docs/akquise/reports").glob(f"*-{vertical}.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    path = files[0]

latest = json.loads(path.read_text(encoding="utf-8"))
if use_server:
    path.unlink(missing_ok=True)

print(f"Report: {path.name if not use_server else 'server'}")
print(f"Stand:  {latest.get('generated_at')}")
diff = latest.get("diff") or {}
print(f"Vergleich: {diff.get('previous') or '— (erster Scan mit Diff)'}")
print(f"Änderungen: {diff.get('changes', 0)} | Trigger: {diff.get('trigger_count', 0)}")
print()

if diff.get("trigger_leads"):
    print("=== ⚡ TRIGGER (seit letztem Scan) ===")
    for n in diff["trigger_leads"]:
        for l in latest["leads"]:
            if l.get("name") == n:
                print(f"  • {n}")
                for t in l.get("triggers") or []:
                    print(f"      → {t}")
                break
    print()

new_leads = [l for l in latest.get("leads", []) if l.get("trigger_type") == "new"]
print(f"=== NEU im Radius ({len(new_leads)}) ===")
for l in new_leads[:20]:
    i = l.get("intent") or {}
    print(f"  • {l.get('name')} — {l.get('address', '')[:45]}")
    print(f"      Budget {i.get('budget_tier')} | Anruf: {i.get('contact_priority')}")
if not new_leads:
    print("  (keine — oder erster Diff-Lauf noch nicht abgeschlossen)")
print()

ads = [l for l in latest.get("leads", []) if (l.get("signals") or {}).get("runs_facebook_ads")]
print(f"=== Meta-Werbung ({len(ads)} erkannt) ===")
for l in ads[:10]:
    i = l.get("intent") or {}
    print(f"  • {l.get('name')} — Budget {i.get('budget_tier')}")
print()

calls = [l for l in latest.get("leads", []) if (l.get("intent") or {}).get("contact_priority") == "call"]
print(f"=== JETZT ANRUFEN — Top 10 von {len(calls)} ===")
for l in calls[:10]:
    i = l.get("intent") or {}
    extra = ""
    if l.get("triggers"):
        extra = " ⚡ " + "; ".join(l["triggers"])
    print(f"  [{i.get('budget_tier')}] {l.get('name')}{extra}")
    print(f"      {i.get('stack_summary', '')[:65]}")

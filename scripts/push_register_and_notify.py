#!/usr/bin/env python3
"""Upload akquise/register.py + send Muamed Safer findings + deploy note."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agency_config import ssh_connect
import paramiko

REPORT = """Update Register/API + Muamed Safer (öffentlich sichtbar auf Northdata):

API-Lage für uns:
1) OpenRegister (empfohlen): Free 500 Credits/Monat, Key unter openregister.de anlegen, dann OPENREGISTER_API_KEY ins Agency-Setup. Code ist vorbereitet.
2) North Data API: Slot existiert schon (NORTHDATA_API_KEY), aber ab ca. 500 €/Monat. Für die Agency aktuell zu teuer.
3) OpenCorporates: inzwischen nur noch mit Token (401 ohne Key).
4) OffeneRegister.de SQL-API: aktuell nicht erreichbar (404).

Was zu Muamed Safer öffentlich steht (Northdata Personenseite, kein bezahlter API-Call):
- PSA Marketing GmbH, Monheim a. Rhein (GF mit Pavel Saper) – passt zum Impressum
- Safer Management GmbH, Monheim (GF Muamed Safer)
- Horizon Cyber Market GmbH, Monheim (GF u. a. Muamed Safer)
- ProOffice - bc Leverkusen GmbH (GF Muamed Safer)
- Hansa Gebäudedienste & Co. GmbH, Haan (GF Muamed Safer)
- CC Stadthotel GmbH, Köln (Prokura / früher GF)
- Chaquiri Invest Holding GmbH, Düsseldorf (im Netzwerk gelistet)
- Care4You Assistenz GmbH, Düsseldorf (im Netzwerk)
- IVK Global Trading GmbH, Monheim (im Netzwerk)

Das ist kein vollständiger Handelsregister-Auszug und keine Gesellschafterliste. Für Automation brauchst du den OpenRegister-Free-Key (oder später Northdata Premium/API).

Nächster Schritt von dir: Account auf https://openregister.de/ , Free-Key kopieren, Agency-Setup → Akquise Engine → OPENREGISTER_API_KEY. Dann kann Nils Personen/Firmen per Telegram live abfragen.
"""


def main() -> int:
    c = paramiko.SSHClient()
    ssh_connect(c, timeout=30, banner_timeout=30, role="web")
    sftp = c.open_sftp()
    local = ROOT / "akquise" / "register.py"
    for remote in (
        "/root/app/akquise/register.py",
        "/root/app/backend/../akquise/register.py",
    ):
        pass
    # find existing akquise
    _, o, _ = c.exec_command(
        "find /root/app -path '*/akquise/register.py' 2>/dev/null | head -5; "
        "ls -d /root/app/akquise 2>/dev/null; ls -d /root/akquise 2>/dev/null"
    )
    found = o.read().decode(errors="replace")
    print("found:", found)
    remote = "/root/app/akquise/register.py"
    for line in found.splitlines():
        if line.strip().endswith("register.py"):
            remote = line.strip()
            break
    # ensure dir
    c.exec_command(f"mkdir -p {remote.rsplit('/',1)[0]}")
    print("upload ->", remote)
    sftp.put(str(local), remote)
    with sftp.file("/tmp/nils_register_update.txt", "w") as f:
        f.write(REPORT)
    sftp.close()

    cmd = r"""
cd /root/app/backend && PYTHONPATH=/root/app:/root/app/backend /root/app/venv/bin/python <<'PY'
import os
from pathlib import Path
for p in (Path('/root/app/backend/.env'), Path('/root/app/deploy.secrets.local')):
    if not p.exists(): continue
    for line in p.read_text(errors='replace').splitlines():
        s=line.strip()
        if not s or s.startswith('#') or '=' not in s: continue
        k,v=s.split('=',1)
        os.environ[k.strip()] = v.strip().strip('"').strip("'")
import telegram_ops
from akquise import register as reg
print('readiness', reg.readiness())
text=Path('/tmp/nils_register_update.txt').read_text(encoding='utf-8')
print(telegram_ops.notify_owner(text))
PY
"""
    _, o, e = c.exec_command(cmd, timeout=60)
    print(o.read().decode(errors="replace")[:3000])
    err = e.read().decode(errors="replace")
    if err.strip():
        print("ERR", err[:1500])
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

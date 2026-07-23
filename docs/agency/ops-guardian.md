# Ops-Guardian (Alleskönner, ehrlich)

Stand: 2026-07-19

Du willst einen Alleskönner. Der Guardian ist die ehrliche Version davon:

- prüft Surfaces (Health, Agency-Setup, B2B, Yassine)
- SSL-Ablauf
- Dual-Status (lokal)
- Resource (RAM/Disk/Dienste) auf dem Server
- WhatsApp-Readiness (nur Melden, kein Meta-Kauf)
- **Safe-Fix:** snack-api Restart (max 2/h) wenn Health rot
- Mail an dich bei Gelb/Rot (Cooldown 4h, kein Spam)

## Was er bewusst nicht macht

- Domains kaufen, Meta-Tokens besorgen, Anwalt ersetzen
- Blind Auth/Zahlung retryen
- Soft-404 „wegzaubern“ ohne Deploy-Fix

Andere Crons bleiben: Nightly, Route, Resource, Dual, Portal. Der Guardian **orchestriert und meldet zentral**.

## Nutzung

```bash
python scripts/ops_guardian_cli.py run
python scripts/ops_guardian_cli.py status
```

API: `GET /api/nils/guardian` · `POST /api/nils/guardian/run`  
Cron web: `*/15` → `scripts/ops_guardian.sh`  
Setup: `python scripts/setup_ops_guardian.py`

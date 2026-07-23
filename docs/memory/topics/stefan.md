# Topic: Stefan Betriebsleiter

Stand: 2026-07-17

## Rolle

**Stefan** = Betriebsleiter / Treiber. Führt Nils und künftige Mitarbeiter. Christian = Inhaber.

## Dateien

- Sheet: `docs/agency/stefan.md`
- Regel: `.cursor/rules/stefan.mdc` (alwaysApply)
- Skill: `.cursor/skills/stefan/SKILL.md`
- Stellenplan aktualisiert

## Nils

Regel `nils.mdc` jetzt `alwaysApply: false` (unter Stefan, bei Ops-Themen).

## 24/7 Morgen-Digest

**Live** auf auto-01neu:

- Cron `0 7 * * *` → `stefan_morning_digest.sh`
- Test-Mail 17.07. gesendet (alle Checks OK)
- Setup: `python scripts/setup_stefan_digest.py --send`

## Nils

Regel `nils.mdc` jetzt `alwaysApply: false` (unter Stefan, bei Ops-Themen).

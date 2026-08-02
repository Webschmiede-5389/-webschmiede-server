# Step 4 — A/B Test Comparison

## Methode

| Seite | Commit | Runner |
|-------|--------|--------|
| A Pre-Pilot | `ee1da86` (git worktree `crm-ab-pre-pilot`) | gleiches `.venv-step4`, gleiche Flags |
| B Pilot+Fix | CRM branch + Step-4 Isolation | `run_crm_full_test_suite_isolated.ps1` |

Evidence: `evidence/step-4/full-suite-ab-pre-pilot.txt` vs `full-suite-after-fix.txt`

## Ergebnis

| Metrik | Pre-Pilot `ee1da86` | Pilot+Step4 |
|--------|--------------------|-------------|
| passed | 80 | **246** |
| failed | 1 | **0** |
| errors | 23 | **0** |
| exit | ≠0 | **0** |

Hinweis: Pre-Pilot-Worktree enthält weniger Test-Dateien (nur committed Stand); Untracked-Tests im Pilot-Working-Tree erhöhen die Anzahl. Trotzdem: Isolation-Fehler (slug UNIQUE, Placetel nonce) auf Pre-Pilot **ohne** Branding-Commit reproduziert → **kein Branding-Regression-Nachweis**.

## Fazit

Suite-Blocker waren Environment/Fixture-Isolation + fehlendes alembic in System-Python, nicht Login/AppShell/Dashboard-Markup.

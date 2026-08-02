# Nils Entity-Routing / Current-Turn-First

Stand: 2026-08-02

## Fakten

- Bug: „Lege Hassan…“ mapte nicht → LLM übernahm mbp-Kontext.
- Fix: Intent + `turn_routing.py` Guards + Resume-Gate + Promise-Guard.
- Staging-Canary A–E: **16/16 PASS**, Staging-DB sqlite, Owner-Allowlist.
- Nach Canary: Code bleibt, CRM wieder postgres-Read, `NILS_CAP_CRM_PROSPECT_CREATE=0`.

## Nächster Schritt

Limited-Production nur nach gesonderter Freigabe (Prospect-Write wieder an + Monitoring).

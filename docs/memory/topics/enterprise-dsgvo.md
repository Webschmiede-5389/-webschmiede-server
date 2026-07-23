# Enterprise DSGVO

Stand: 2026-07-21

## Beschluss

- Bleiben beim eigenen Portal (kein Budibase-Pflicht)
- Live-Hosting: Hetzner **Frankfurt/Nürnberg**, nicht Helsinki
- Zero-Retention 24h im B2B-Portal (Default an)
- Anwalt-Enterprise-API bereitet DocuSeal-Felder vor, ersetzt keinen Anwalt
- **AVV optimiert (2026-07-21):** n8n explizit als Gegenstand, KI-Modelltraining-Ausschluss (§ 5a), erweiterte TOMs (Docker-Isolation, TLS 1.3, Encryption at Rest, MFA), Subunternehmer-Tabelle mit Widerspruchsfrist 14 Tage, Haftungsabgrenzung bei kundeneigenen APIs, KI-Routing-Transparenz (lokal vs. EU-Enterprise)

## Offen Christian

1. Hetzner AVV in Console laden (`docs/agency/hetzner-avv.md`)
2. Anwalt gegenlesen lassen (`ANWALT-BRIEFING.md` – jetzt mit n8n/KI-Punkten 10–15)
3. Gewünschte Formate: ausfüllbares PDF/Word + digitale Klickversion

## Dateien

- `docs/agency/enterprise-dsgvo.md`
- `docs/agency/anwalt-pipeline.md`
- `app/backend/agency_anwalt.py` (enterprise + 3 Stufen)
- `scripts/anwalt_pipeline_cli.py`
- `scripts/harden_n8n_logs.py`
- `infra/n8n/agency-system/10-anwalt-pipeline.json`

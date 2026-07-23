# Halluzinations-Versicherung

Stand: 2026-07-20

## Live

- Modul `nils_truth.py`: FACT_POLICY, grounding_block, soft flags, honesty_footer
- Drin in: human_voice, companion, finalize, orchestrator, Cursor-Prompt, Golf/Draft-Tools
- Seed `pref.truth` im Langzeitgedächtnis

## Regel

Nur belegte Quellen (Tools/Gedächtnis/Live). Unbekannt = ehrlich. Keine erfundenen Status/Preise/Mails/Deploys.

## Betriebs-Tipps (für Christian)

1. Code oft pushen (Cloud-Agent sieht nur GitHub)
2. Requesty Hard-Limit $20 in Console
3. Freigabe bei Mail/Cursor/Bild ernst nehmen
4. Shipcheck vor Kunden-Links
5. `merk dir:` für echte Dauerfakten
6. n8n Webhook erreichbar halten wenn Orchestrator triggern soll

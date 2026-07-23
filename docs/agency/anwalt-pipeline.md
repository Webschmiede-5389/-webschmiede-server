# Anwalt 3-Stufen-Pipeline

Stand: 2026-07-19

## Prinzip

Nicht ein Rutsch „Vertrag fertig“, sondern:

1. **Vertrags-Architekt** – Hauptteil B2B  
2. **Compliance-Wächter** – AVV Art. 28 + TOMs  
3. **Endkontrolle** – Checkliste, Ampel, Findings  

## Wahrheit (gegen Guru-Pitch)

| Claim im Pitch | Realität |
|----------------|----------|
| Helsinki | **Nein** – Hetzner **Nürnberg** |
| Wasserdicht / astrein | **Nein** – KI-Vorprüfung, `rechtskraft: false` |
| Claude/GPT-Nodes Pflicht | **Nein** – deterministische Agency-API; LLM nur nach OK+Key |
| Auto-PDF an Kunden | **Nein** – Christian prüft, dann DocuSeal |

## Nutzung

```bash
python scripts/anwalt_pipeline_cli.py --firma "Mueller GmbH" --budget "5000" \
  --leistungen "Wholesale-Listen via Keepa, eigenes Dashboard" --out vertrag.md
```

API (Agency-Auth):

- `POST /api/agency/anwalt/pipeline` – alle 3 Stufen
- `POST /api/agency/anwalt/stage/1|2|3` – einzeln (n8n-Kette)
- `POST /api/agency/anwalt/enterprise` – DocuSeal-Felder / Vendor-Pack

n8n (inaktiv importieren): `infra/n8n/agency-system/10-anwalt-pipeline.json`

System-Prompts fuer spaetere LLM-Nodes liegen in der API-Antwort unter `system_prompts`
(mit Nürnberg, ohne Wasserdicht-Claims).

## Stufe 3 = Endkontrolle (Lektor-Recht)

Stufe 3 ist die „unbestechliche“ Pruefung (Haftung, Standort, AVV, Claims).  
Sprach-Lektor (Texter-Skill) ist optional danach, ersetzt Stufe 3 nicht.

## Nach der Pipeline

1. Ampel lesen  
2. DocuSeal Kundenpaket befüllen  
3. Hetzner-AVV in Akten  
4. Enterprise: echter Anwalt (`ANWALT-BRIEFING.md`)

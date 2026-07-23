# Agency-Hirn scharf

Stand: 2026-07-19

## Beschluss

Router klassifiziert nicht nur, sondern **dispatched** (Stefan, Scout, Nils, …).  
Cursor-Chat wird nicht magisch mitgelesen – Agent nutzt Hirn-API/CLI + Rule `agency-brain.mdc`.

## Live

- `POST /api/agency/brain`
- `python scripts/agency_brain_cli.py "…"`
- n8n aktiv: Hirn, Router, Stefan (auto)
- **Cursor eingestellt:** `.cursor/hooks.json`  
  - `beforeSubmitPrompt` → schreibt `.cursor/brain-routing.md`  
  - `sessionStart` → injiziert Hirn-Kontext  
  - Rule `agency-brain.mdc` Pflicht: Routing-Datei lesen

## Grenze

Kein Auto-Send. Texter/Design/Lektor = Cursor-Skills laut Playbook.  
Neuen Chat oeffnen damit Hooks greifen.

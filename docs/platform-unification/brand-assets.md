# Brand Assets (aktualisiert SCHRITT 2)

## Kanonisch

Verzeichnis: `app/static/brand/webschmiede/`  
Manifest: `app/static/brand/webschmiede/manifest.json`

| Asset | Pfad | Bemerkung |
|-------|------|-----------|
| Wortmarke | `/brand/webschmiede/logo-horizontal.png` | Byte-Kopie von `/ci/webschmiede-logo.png` |
| Mark | `/brand/webschmiede/logo-mark.png` | Kopie von `/ci/webschmiede-logo-mark.png` |
| Favicon | `/brand/webschmiede/favicon.png` | Resize aus Mark |
| App 192/512 | `/brand/webschmiede/app-icon-*.png` | Resize aus Mark |

**SVG:** nicht vorhanden, **nicht** neu gezeichnet (`svg_status: unavailable_no_redraw`).

CI-Originale unter `/ci/` bleiben (nicht gelöscht). Legacy horizontal/icon weiterhin deprecated.

## Kundenlogos

Unverändert unter `app/static/brand/{slug}-logo.png` (z. B. snackhouse).

## Setup

```bash
python scripts/setup_brand_assets.py
```

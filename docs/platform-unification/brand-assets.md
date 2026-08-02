# Brand Assets Audit

**Stand:** 2026-08-02 · Read-only  
**Kanonische CI-Doku:** `docs/agency/ci/BRAND.md`

## Öffentliche Website (agency-web)

| Asset | Pfad | Format | Auflösung | Hinweis |
|-------|------|--------|-----------|---------|
| Wortmarke | `agency-web/public/webschmiede-logo.png` | PNG | 1114×268 · ~216 KB | Live-Marke |
| Horizontal Agency | `agency-web/public/webschmiede-logo-horizontal-agency.png` | PNG | 1114×268 · ~216 KB | Duplikat der Wortmarke |
| Mark | `agency-web/public/webschmiede-logo-mark.png` | PNG | (Kopie CI) | Icon |
| Favicon | `agency-web/public/favicon.png` | PNG | 1024×1024 · ~359 KB | groß; SVG Favicon fehlt |

## Agency Cockpit

| Verwendung | Pfad |
|------------|------|
| Login + Sidebar Mark | `/ci/webschmiede-logo-mark.png` → `app/static/ci/webschmiede-logo-mark.png` (623×602 · ~316 KB) |
| Favicon | gleiches Mark |
| Textlockup | „WebSchmiede“ + „Digitale Handwerkskunst“ (HTML, nicht im Bild) |

## Server CI-Ordner (`app/static/ci/`)

| Datei | Größe | Rolle laut BRAND.md |
|-------|-------|---------------------|
| **webschmiede-logo.png** | 1114×268 | **Kanonische Wortmarke** |
| **webschmiede-logo-mark.png** | 623×602 | **Kanonisches Markenzeichen** |
| webschmiede-logo-horizontal.png | 308×308 | **Legacy** — nicht als Hauptlogo |
| webschmiede-logo-horizontal.jpeg | vorhanden | **Legacy** |
| webschmiede-logo-icon.png | 615×410 | **Legacy** (Padding) |
| webschmiede-logo-icon-transparent.png | vorhanden | prüfen / ggf. Mark ersetzen |
| webschmiede-icon.png | vorhanden | Alt |
| vc-qr.png | QR Visitenkarte | ok |
| christian-kummetat.jpg | Foto | CI Vorlagen |

## Kundenlogos

| Datei | Tenant |
|-------|--------|
| `app/static/brand/snackhouse-yassine-logo.png` | SHY001 |
| `app/static/img/logo.png` | SHY001 Shop |

## Problematische / abweichende Marken

| Ort | Problem |
|-----|---------|
| CRM `base.html` `.brand-mark` | Orangenes Quadrat mit Buchstabe **„W“** — kein offizielles Logo |
| CRM Login | Buchstabe **„A“** im Mark |
| Lead Creator `base.html` | Inline-SVG Wortmark „Digitale Handwerkskunst“ + Hammer-Icon, Farbe `#E8600A` |
| Lead Creator `dashboard/static/logo.svg` | Eigenes SVG |
| Preview Studio | Emoji 👁, Gold `#C9A84C`, kein CI-Logo |
| Sales Dashboard | Wortmarke auf **braunem** Dark-Theme |
| Shop/Admin | Gold `#C9A84C` — **korrekt für Kundenmodus**, nicht Agency |

## Fehlende kanonische Varianten

- `logo-horizontal.svg` / `logo-mark.svg` / `favicon.svg` — **nicht vorhanden** (nur PNG)  
- Explizite „dark-on-light“ vs „light-on-dark“ Wortmarken-Paare — unklar; aktuelle PNGs sind dunkel+orange auf Transparent  
- App-Icon-Set für CRM PWA liegt unter `crm/app/static/icons/` (separat prüfen, oft generiert)

## Vorgeschlagene kanonische Struktur (an bestehende Architektur)

Bestehende Auslieferung läuft über Nginx Static unter `/ci/` und agency-web `public/`.  
**Keine zweite parallele Library.** Vorschlag:

```
app/static/ci/branding/webschmiede/   # oder Alias-Pfade unter bestehendem /ci/
  logo-horizontal.png     → symlink/copy von webschmiede-logo.png
  logo-mark.png           → webschmiede-logo-mark.png
  favicon.png             → abgeleitetes 32/192 aus Mark (optimiert)
  app-icon-192.png
  app-icon-512.png
```

Optional später (nach Export aus Originalquelle, keine Neuerfindung):

```
  logo-horizontal.svg
  logo-mark.svg
  favicon.svg
```

**Referenz in Apps:** immer `/ci/webschmiede-logo.png` bzw. `/ci/webschmiede-logo-mark.png` — keine lokalen Kopien in CRM/Leads, wenn Shared Static erreichbar; sonst Build-Step kopiert aus CI-Quelle.

## Regeln (unverändert aus BRAND.md)

1. Nur freigestellte `webschmiede-logo.png` / `webschmiede-logo-mark.png`  
2. Nie horizontal/icon-Legacy als Hauptlogo  
3. Kein Logo neu zeichnen, solange offizielle Dateien existieren  
4. Kundenlogos ersetzen **nie** das Agency-Logo in AGENCY_INTERNAL / AGENCY_CUSTOMER_MANAGEMENT

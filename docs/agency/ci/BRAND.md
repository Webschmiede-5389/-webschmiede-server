# Webschmiede Corporate Identity

> **Orange & Weiß** · **Inter** · Kein Snack-House-Gold, keine Playfair-Schrift.

## Live

| Was | URL |
|-----|-----|
| Agency Hub | https://digitalehandwerkskunst.de/agency-hub |
| Visitenkarte (1:1 PDF) | /ci/visitenkarte-vorlage.html |
| Admin | /agency |

## Farben

| Token | Hex | Verwendung |
|-------|-----|------------|
| Orange | `#FF6600` | Primär, Buttons, Akzente |
| Orange soft | `#FFF4ED` | Hintergründe, Pills |
| Weiß | `#FFFFFF` | Dashboard, Dokumente |
| Ink | `#1A1A1A` | Fließtext |

## Schrift

Nur **Inter** (Bunny Fonts). Kein Playfair Display.

## Logo (verbindlich)

**Nur diese freigestellten Dateien verwenden.** Kein Weißrand, kein schwarzer Padding-Rahmen.

| Asset | Pfad | Verwendung |
|-------|------|------------|
| **Wortmarke (Standard)** | `/ci/webschmiede-logo.png` | Header, Handbuch, Onboarding, Angebote, Rechnungen, Flyer |
| **Markenzeichen (nur Icon)** | `/ci/webschmiede-logo-mark.png` | Kleine Quadrate, App-Mark, wo Text nicht passt |
| Favicon / Mark | `/ci/webschmiede-logo-mark.png` | Browser-Tab, quadratische Plätze |

### Regeln für Agenten

1. **Immer** `webschmiede-logo.png` für horizontale Logos in UI und Druck.
2. **Nie** die alten Dateien als Hauptlogo: `webschmiede-logo-horizontal.png`, `webschmiede-logo-horizontal.jpeg`, `webschmiede-logo-icon.png` (haben Padding / falsches Format).
3. Logo per CSS mit `height` oder `width` + `object-fit: contain` skalieren, **kein** Extra-Padding um das Bild.
4. Auf weißem Papier und hellem UI: Wortmarke ist dunkel + Orange, Hintergrund transparent.

## Visitenkarte

- Wortmarke: `webschmiede-logo.png`
- QR: `vc-qr.png` (orange, digitalehandwerkskunst.de)

Layout: Vorderseite weiß/orange-Split wie PDF · Rückseite Logo + QR + Pipeline-Zeile.

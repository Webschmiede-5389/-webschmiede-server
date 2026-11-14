# Webschmiede Website-Pilot · 14.11.2026

## Auftrag und Grenze
Vollständiger Gestaltungsentwurf für digitalehandwerkskunst.de: Art Direction, Copy, eigene Ablaufillustration, echtes Portrait, kurze Motion, Desktop-/Mobilansichten und Browserprüfung. Finish-Linie: bedienbare private Abnahmevorschau. Keine Änderung an bestehender Homepage, Backend, Kundensystemen, DNS oder Deployment-Workflows.

WEBSCHMIEDE_RULESET_SHA=01089a98bfdff44bdc9ea346cb21696298418170
Quellbasis: Webschmiede-5389/-webschmiede-server, main 330f3ad627883cd6ff0a62094e1b54f9b1debbb3.
Branch: design/webschmiede-pilot.

## Wichtiger Befund zur Quellenlage
Die öffentlich sichtbare Website am 14.11.2026 stimmt NICHT mit agency-web/src/pages/HomePage.tsx dieser Basis überein. Live: Du-Ansprache, Hero „Weniger Chaos im Betrieb…“, Telefonnummer +491791598184, Kundenlogin /login. Repository: ältere Sie-Ansprache, andere Telefonnummer. Der aktuelle Produktions-Build ist keinem geprüften Commit zugeordnet. Deshalb keine Ersetzung der bestehenden Startseite und kein Release. Der Entwurf ist ein isolierter HTML-Einstieg; bestehende Routen, Kontaktkonfiguration und Rechtstexte bleiben unverändert. Im Entwurf werden die aktuell live beobachteten Kontaktziele und Rechtstext-URLs benutzt. Vor Übernahme zuerst aktuelle Produktionsquelle zuordnen; keine alten Inhalte zurücksetzen.

## Art Direction und Seitenvertrag
Orange/Weiß/Inter gemäß docs/agency/ci/BRAND.md. Wortmarke aus app/static/ci/webschmiede-logo.png, Portrait aus agency-web/public/christian-kummetat.jpg. Keine generierten Personen, Logos, Testimonials oder Erfolgszahlen. Inter lokal, OFL-Lizenz beigelegt. Warme Werkstattflächen, große Typografie, feine Trennlinien, dunkler interaktiver Hauptteil. CTA-Kontrast geprüft: Hintergrund #f05c00 zu Weiß (große Schrift) 3,37:1 und Ink #24231f (kleine Schrift) 4,67:1.

| Abschnitt | Besucherfrage | Inhalt / Bild | Bedienung / Bewegung |
|---|---|---|---|
| Einstieg | Was hilft mir das? | Betrieb und Büro; Nachrichten ordnen sich zur Ablaufillustration | Gespräch / Ablauf ansehen; Linie zeichnet sich einmal |
| Alltag | Ist das mein Problem? | Anfragen, Büro nach Feierabend, fehlender nächster Website-Schritt | Ruhiger Leseteil |
| Ablauf | Wie könnte das aussehen? | Vier Branchen, je drei illustrative Zustände | Branchenwahl und Schrittwechsel; kurze Einblendung |
| Leistungen | Was kann ich beauftragen? | Website, betrieblicher Ablauf, Automatisierung | Kontaktverweise |
| Christian | Wer kümmert sich? | Originalportrait, belegter Trockenbau-Hintergrund | Direkter Telefonlink |
| Zusammenarbeit | Was kommt auf mich zu? | Gespräch, Entwurf/Test, Freigabe/Einweisung | Verständliche Folge ohne erfundene Leistungsfristen |
| Fragen | Was kostet es, was bleibt bestehen? | Umfang, Anbindungen, Betreuung, Daten | Native aufklappbare Antworten |
| Kontakt | Wie fange ich an? | Konkrete Frage nach liegenbleibender Arbeit | Bestehende Buchung, WhatsApp, Mail, Telefon |

Mobile: gestapelte Illustration und Inhalte, Branchenwahl 2x2, eigenes Menü mit Escape und Fokusführung. Reduced-Motion-Regel deaktiviert Animationen und weiches Scrollen. Der Branchenablauf ist ausdrücklich ein Beispiel, kein Produkt-Funktionsbeweis.

## Starten / Bauen
Im Ordner agency-web:

```sh
npm ci
npx tsc --noEmit
npx vite build --config vite.pilot.config.ts
npm run dev
```

/pilot.html: vollständiger Entwurf.
/review.html: echte Browser-Frame-Ansichten bei 360, 390, 768 und 1440 px. Für Tests feste Höhe, für visuelle Abnahme „Ganze Seite anzeigen“. Kein physischer Gerätetest.
Buildziel: dist-pilot. Standardbuild und bestehende index.html/App.tsx/HomePage.tsx bleiben unangetastet. Der private Review-Host erhält ausschließlich diesen statischen Pilot-Build mit lokaler Schrift, Logo und Portrait; keine Server-/Kundendaten. Dies ist ein austauschbarer Vorschau-Spiegel, keine neue Produktionsplattform.

## Browsernachweise
Geprüft mit Chrome im tatsächlichen laufenden Vite-Preview:
- Desktop 1348 px: ganze Seite visuell geprüft.
- Frames 360/390/768/1440 px: kein horizontaler Überlauf (345/375/753/1425 px Inhaltsbreite wegen 15 px Scrollbar).
- Alle vier Branchen jeweils Schritt 1 → 2 → 3 → Neustart: richtige Texte und Status sichtbar.
- Mobiles Menü: öffnen, schließen mit Escape, Sprung zum Alltag; Menü danach geschlossen.
- Mobiler Dienstleistungsablauf Schritt 1 → 2: bestätigt.
- Alle fünf FAQ: sichtbar geöffnet; interne Anker ohne fehlende Ziele.
- Alle vier Bildinstanzen nach Scrollen geladen. Footerbild ist lazy-loaded.
- TypeScript und Vite-Pilotbuild bestanden.
- Browserprotokoll: Fehler aus Chrome-Erweiterung „Error sending browser metadata to extension“, keine als Appfehler identifizierten Einträge. Kein pauschaler Beleg eines fehlerfreien Browsers.
- Gefundener Fehler: Wörter an auf Mobil verstecktem Zeilenumbruch liefen zusammen. Korrigiert und erneut visuell geprüft.
- Review-Harness zunächst mit ganzseitiger Framehöhe: ungeeignet für Menüinteraktion. Auf feste Gerätehöhe plus explizite Ganzseitenansicht geändert; Menütest wiederholt bestanden.

## Status und nächste Handlung
- CODE_PASS: TypeScript / isolierter Produktionsbuild.
- UI_PASS: oben aufgeführte Browserwege.
- HUMAN_USABILITY_OPEN: Christian prüft Wirkung, Sprache und Verständlichkeit des vollständigen Entwurfs.
- PRODUCTION_SOURCE_OPEN: Zuordnung der aktuellen Live-Quelle fehlt.
- RELEASE_NOT_REQUESTED: kein Merge, kein Production-Deploy, keine DNS-Änderung.
- Produktionsstraße NICHT freigegeben: ein geprüfter Entwurf ist noch kein Beleg für wiederholbare Lieferqualität oder Conversion-Wirkung.

Nicht geprüft: physische iOS/Android-Geräte, vollständiges WCAG-Audit, Lighthouse/Felddaten, echte Terminbuchung, Nachrichtenzustellung, Live-Backend, Formulare oder Conversion-Erfolg. Externe Kontaktwege wurden nicht testweise ausgelöst.

Nächster Schritt: Christian beurteilt den privaten vollständigen Entwurf. Vor einer tatsächlichen Übernahme muss die aktuelle Produktionsquelle abgeglichen werden. Kein Neubau weiterer Skills oder Tools erforderlich.

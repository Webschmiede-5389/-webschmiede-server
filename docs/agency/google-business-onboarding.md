# Google Business Profil · Anschluss & Review-Automation

## Was wir wollen

1. Gäste bewerten über Link / Theken-QR  
2. Neue Bewertungen automatisch (oder halbautomatisch) beantworten  
3. Antworten mit echten, lokalen Keywords (Ort, Gerichte, Service), ohne Spam-Text  
4. Das hilft Sichtbarkeit im lokalen Google, zusammen mit frischen Bewertungen und aktivem Profil  

## Wie der Kunde uns Zugang gibt (wichtig)

**Nie das Google-Passwort abfragen oder speichern.** Das ist unsicher und gegen Googles Regeln.

### Weg A – Sofort nutzbar (empfohlen zum Start)

Kunde bleibt Inhaber. Er lädt WebSchmiede als **Manager** ein:

1. Google Unternehmensprofil öffnen (business.google.com)  
2. Nutzer hinzufügen → E-Mail von WebSchmiede (z. B. Agency-Mail)  
3. Rolle **Manager**  
4. Christian nimmt die Einladung an  

Dann können wir Bewertungen sehen und antworten (manuell oder später per Tool).

### Weg B – Später: „Mit Google verbinden“ (OAuth)

Kunde klickt im Onboarding **Google verbinden**. Google-Login-Fenster öffnet sich **bei Google**.  
Er meldet sich selbst an und erlaubt unserer App den Scope `business.manage`.  
Wir speichern nur **Tokens** (Access + Refresh), kein Passwort.

Voraussetzungen auf unserer Seite:

- Google Cloud Projekt  
- Business Profile APIs aktiv  
- OAuth Client + Consent Screen  
- Oft: Freigabe / Quota bei Google beantragen (kann Tage bis Wochen dauern)  

## Was der Kunde im Onboarding einträgt (ohne Passwort)

| Feld | Zweck |
|------|--------|
| Google-Bewertungslink | Für SMS/QR nach der Bestellung |
| Google-Konto-E-Mail (Inhaber) | Damit wir die Manager-Einladung richtig zuordnen |
| Status | offen / Link da / Manager eingeladen / OAuth verbunden |

Optional später: Place-ID, Standort-Name.

## Automation (Soll)

1. Neue Bewertung erkannt (API oder Benachrichtigung)  
2. Sterne + Text lesen  
3. Antwort vorschlagen oder senden: Dank + 1–2 lokale Keywords (Ort, Spezialität), höflich, kein Keyword-Stuffing  
4. Log in Agency / Kundenakte  

**Stand jetzt im Repo:** Review-Link + Follow-up-SMS möglich. Auto-Antwort per API noch **nicht** gebaut. Manager-Zugang (Weg A) ist der schnelle Start.

## Onboarding

Abschnitt **Google Unternehmensprofil** in `onboarding.html`.  
API: `POST /api/onboarding/<kid>/google`  
Daten: `kunden/*.json` → Block `google`.

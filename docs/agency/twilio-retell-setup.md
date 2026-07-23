# Twilio + Retell (DE-Nummer für Voice-Sekretärin)

Stand: 2026-07-17

Retell verkauft **keine** DE-Nummern direkt (nur US/CA). Für Deutschland: Twilio → Elastic SIP → Nummer in Retell importieren.

## Kosten (Richtwert)

- Ortsnummer DE: ca. **1,35 $/Monat**
- Retell KI: ca. **0,15–0,20 $/Min.**
- Twilio eingehend: ca. **0,01 $/Min.**

## Was Christian macht (Account + Freigabe)

Twilio braucht **Firma** (Gewerbe/Handelsregister). Privat geht für DE-Nummern nicht.

1. Account: https://www.twilio.com/try-twilio  
   Firma Webschmiede / Digitale Handwerkskunst, echte Mail, Karte hinterlegen.
2. Console → **Phone Numbers** → **Regulatory Compliance** → Bundle für **Germany** / Local.  
   Hochladen: Gewerbeanmeldung oder Handelsregisterauszug + Adresse in DE.  
   Warten bis Status **Approved** (kann Tage dauern).
3. Wenn freigegeben: **Buy a number** → Germany → Local Voice → eine Nummer kaufen (~1,35 $/Mo).
4. Keys notieren (nicht im Chat posten, in Agency Setup speichern):
   - Account SID (`AC…`)
   - Auth Token
   - Gekaufte Nummer im Format `+49…`

Danach Bescheid: „Twilio SID + Nummer liegen in Agency Setup“ **oder** Keys selbst unter `/agency-setup` eintragen.

## Was wir danach machen (SIP + Retell)

1. Twilio → **Elastic SIP Trunking** → Trunk anlegen (z. B. `webschmiede-retell`).
2. **Termination** (Outbound Richtung Retell → PSTN): Twilio Termination URI notieren.
3. **Origination** (Inbound PSTN → Retell):  
   `sip:sip.retellai.com;transport=tcp`
4. Gekaufte Nummer dem Trunk zuweisen.
5. In Retell Nummer importieren (`/import-phone-number`) mit Termination-URI + Auth falls gesetzt.
6. Inbound-Agent setzen (z. B. Demo-Sekretärin oder Jay-Test).
7. Probeanruf von Christians Handy → Gespräch → Log prüfen.

Skript (wenn Keys da): `python scripts/setup_twilio_retell_number.py` (sobald Keys in Secrets).

## Secrets (Agency Setup)

| Key | Bedeutung |
|-----|-----------|
| `TWILIO_ACCOUNT_SID` | Account SID |
| `TWILIO_AUTH_TOKEN` | Auth Token |
| `TWILIO_VOICE_NUMBER` | E.164 z. B. `+4922…` |
| `TWILIO_SIP_TRUNK_SID` | optional, nach Trunk-Anlage |
| `TWILIO_SIP_TERMINATION_URI` | für Retell-Import |

## Nicht verwechseln

- **seven.io** = SMS (bleibt)
- **Twilio** = Telefonie / Rufnummer für Retell
- **Jay Web-Call** = ohne Twilio, nur Browser

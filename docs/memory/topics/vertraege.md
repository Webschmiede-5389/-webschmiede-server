# Verträge / DocuSeal

Stand: 2026-07-18

## Status

**CI:** Header oben weiß, Logo ohne Card, Titel schwarz, orangene Linie. Rest orange wie gehabt.

**Kunden-Flow:** fertig für Standardfall.

| Wunsch | Stand |
|--------|--------|
| Prefill Firma/Datum/Preise | OK via `send_vertraege_kunde.py` |
| Ein Link, Auftrag+AGB+AVV | OK (`ws-kundenpaket`) |
| Deine Unterschrift vorausgefüllt | OK (`assets/unterschrift-christian.png`) |
| Kunde nur eigene Felder | OK |
| SMTP-Mail | optional; bei Problemen `--no-email` + Link schicken |

## Senden

```bash
python scripts/send_vertraege_kunde.py --firma "..." --email "..." --setup 998 --monat 298
```

Test-Link zuletzt: siehe `_last_send.json`

## Nächster Schritt

WhatsApp (Meta) – Verträge erstmal so lassen. Echte Hand-Signatur optional als PNG ersetzen.

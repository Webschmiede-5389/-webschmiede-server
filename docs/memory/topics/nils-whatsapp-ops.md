# Topic: Nils via WhatsApp (Ops-Kanal)

Stand: 2026-07-19  
Code live: `nils_whatsapp_ops.py` · Webhook routet Owner → Nils.

## Zielbild

Christian privat → Business-Nummer → Nils antwortet (Status, Aufträge, Fotos).  
Fremde → kurze Absage. Kunden-Portale weiter über eigene Tenant-Nummern.

## Nummern

- Business = Meta Cloud API (= Nils)
- Privat = Absender, muss in `OWNER_PHONE` / `NILS_OPS_OWNER_PHONES` stehen

## Christian jetzt

Go-Live: `docs/agency/whatsapp-go-live.md`  
1. Meta Token + Phone Number ID  
2. Webhook messages  
3. OWNER_PHONE setzen  
4. Ping: „Nils Status“

## Sicherheit

Nie blind Deploy. Owner-Whitelist. Signatur wenn META_APP_SECRET gesetzt.

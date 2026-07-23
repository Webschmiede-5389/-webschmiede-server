# Topic: INWX Domain-API

Stand: 2026-07-17

## Beschluss

Domains (inkl. `.de`) über **INWX** kaufen und DNS dort setzen. Cloudflare nicht nötig für den Komfort-Stack.

## Code live (lokal)

- `app/backend/integrations/inwx.py`
- `scripts/provision_domain_inwx.py`
- Agency Setup Felder + Test
- `docs/agency/inwx-domains.md`

## Christian einmalig

1. Account https://www.inwx.de
2. Guthaben + Kontakt anlegen → CONTACT_ID
3. In `deploy.secrets.local`:
   - `INWX_USER=`
   - `INWX_PASSWORD=`
   - `INWX_CONTACT_ID=`
4. `python scripts/provision_domain_inwx.py --test`
5. Dann Yassine: `python scripts/provision_domain_inwx.py snackhouse-yassine.de --ssl`

## Kauf-Regel

Weiterhin nur nach ausdrücklicher Freigabe bzw. `DOMAIN_AUTO_PURCHASE=1`.

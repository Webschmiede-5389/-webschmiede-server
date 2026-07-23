# INWX: API einrichten (Schritt für Schritt)

Für Christian. Ziel: drei Werte in Agency Setup, dann kann Nils Domains prüfen/kaufen (nur nach Freigabe).

Live: https://www.inwx.de (nicht die Test-Seite ote.inwx.de, außer du willst nur üben)

---

## Teil A: Einloggen und Basis

1. Öffne https://www.inwx.de und melde dich an.
2. Wenn die Mail-Bestätigung noch hängt: Support bitten, den Account freizuschalten (hattest du schon).
3. Oben/links ins **Kundenmenü** / Dashboard.

---

## Teil B: Kontakt anlegen (wichtig für Domain-Kauf)

Ohne Kontakt-ID kann die API keine Domain registrieren.

1. Im Menü: **Domains** → **Kontakte** (manchmal „Kontaktverwaltung“ / „Handles“).
2. **Neuen Kontakt anlegen**.
3. Ausfüllen mit Webschmiede / Christian (echte Adresse, wie auf Gewerbe).
4. Speichern.
5. Die **Kontakt-ID** notieren (eine Zahl, z. B. `12345678`).  
   Steht in der Kontaktliste oder in der Detailansicht.

Das wird bei uns: `INWX_CONTACT_ID`

---

## Teil C: API-Zugang (Benutzer + Passwort)

INWX DomRobot nutzt **Benutzername + Passwort** (kein separates „API-Key“-Feld wie bei Cloudflare).

### Variante 1 (einfach): Hauptaccount

1. Merke dir deinen **Login-Benutzernamen**.
2. Das **Passwort**, mit dem du dich einloggst.  
   Wenn 2FA (SMS/App) aktiv ist: API-Scripts scheitern oft. Dann Variante 2.

### Variante 2 (empfohlen bei 2FA): Extra-User nur für API

1. Suche im Menü nach **Benutzer** / **User** / **Zugang** / **Unterbenutzer**.
2. **Neuen Benutzer anlegen** (z. B. Name `api-webschmiede`).
3. Starkes Passwort setzen.
4. Rechte: Domains + DNS + Kontakte (alles was Domains braucht).
5. **2FA für diesen User aus**, wenn möglich.
6. Diesen User + Passwort notieren.

Das wird bei uns:

- `INWX_USER` = dieser Benutzername  
- `INWX_PASSWORD` = dieses Passwort  

API-Doku (nur zum Nachlesen): https://www.inwx.de/de/help/apidoc

---

## Teil D: Guthaben (für echte Käufe)

1. Menü **Finanzen** / **Guthaben** / **Aufladen**.
2. Ein paar Euro aufladen (Domain-Käufe gehen vom Guthaben).  
   Ohne Guthaben: Check geht, Kauf scheitert.

---

## Teil E: Bei uns eintragen

1. Öffne https://digitalehandwerkskunst.de/agency-setup  
2. Agency-Passwort eingeben.
3. Gruppe **Domains (INWX)**:
   - `INWX_USER`
   - `INWX_PASSWORD`
   - `INWX_CONTACT_ID`
4. Speichern.
5. Wenn da: **Test**-Button drücken.

Oder lokal in `deploy.secrets.local` (nicht per Chat schicken).

---

## Teil F: Fertig melden

Schreib mir nur: **„INWX ist drin“**  
(keine Passwörter in den Chat).

Dann teste ich die Verbindung. Domain kaufen weiterhin nur, wenn du es ausdrücklich sagst.

---

## Kurz-Checkliste

- [ ] INWX Live-Login geht
- [ ] Kontakt angelegt → ID notiert
- [ ] User + Passwort (idealerweise API-User ohne 2FA)
- [ ] Guthaben drauf
- [ ] Drei Felder in Agency Setup gespeichert
- [ ] Bescheid an Nils

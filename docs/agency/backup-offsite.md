# Off-Server Backup (Webschmiede)

Täglich nach dem lokalen Backup (`backup_agency.sh`) wird das Archiv per SFTP hochgeladen.

## Hetzner Storage Box (empfohlen)

1. [Storage Box](https://www.hetzner.com/de/storage/storage-box) bestellen (ab ~3 €/Monat)
2. Im Robot: Unteraccount anlegen, Ordner `backups` erstellen
3. Zugangsdaten in **Agency Setup** → Gruppe **Backup (Off-Server)** oder in `deploy.secrets.local`:

```env
BACKUP_SFTP_HOST=u123456.your-storagebox.de
BACKUP_SFTP_USER=u123456
BACKUP_SFTP_PASS=...
BACKUP_SFTP_PATH=backups
```

4. Deploy + einmal testen:

```bash
python setup_backup.py
```

Log: `/var/log/snack-backup.log`  
Erfolg: Zeile mit `offsite ok 2026-07-16 …`

## Manuell auf dem Server

```bash
/bin/bash /root/app/scripts/backup_agency.sh
tail -5 /var/log/snack-backup.log
```

## Watchdog

`nightly_watchdog.py` prüft `backup ok` im Log. Off-Server ist optional (skip wenn nicht konfiguriert).

## Hetzner Storage Box (live)

- Name: `webschmiede-backups` (bx11, Falkenstein)
- Host/User in `BACKUP_SFTP_*` (Port **23**)
- Upload: `scripts/backup_offsite.sh` (python3-paramiko)
- Erfolg im Log: `offsite ok …`

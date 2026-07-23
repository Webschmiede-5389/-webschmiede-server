#!/bin/bash
# Tägliches Agency-Backup + AES-256 (BACKUP_ENCRYPT_PASSPHRASE)
set -euo pipefail
LOG=/var/log/snack-backup.log
BK=/root/app/backups/daily
STAMP=$(date +%Y%m%d_%H%M)
TODAY=$(date +%Y-%m-%d)
SECRETS=/root/app/deploy.secrets.local
mkdir -p "$BK"

_read() {
  grep "^${1}=" "$SECRETS" 2>/dev/null | head -1 | cut -d= -f2- | sed 's/\r$//' | sed 's/^"//;s/"$//'
}

echo "===== backup start $(date -Iseconds) =====" >> "$LOG"

INCLUDE=()
for f in \
  /root/app/backend/orders.db \
  /root/app/kunden \
  /root/app/deploy.secrets.local \
  /root/app/backend/.env \
  /opt/n8n/.env
do
  if [ -e "$f" ]; then
    INCLUDE+=("$f")
  else
    echo "skip missing $f" >> "$LOG"
  fi
done

if [ ${#INCLUDE[@]} -eq 0 ]; then
  echo "backup FAILED ${STAMP} no files" >> "$LOG"
  exit 1
fi

ARCHIVE="$BK/agency-${STAMP}.tar.gz"
tar czf "$ARCHIVE" "${INCLUDE[@]}" 2>>"$LOG"

PASS="$(_read BACKUP_ENCRYPT_PASSPHRASE)"
if [ -n "$PASS" ]; then
  ENC="${ARCHIVE}.enc"
  openssl enc -aes-256-cbc -pbkdf2 -salt -in "$ARCHIVE" -out "$ENC" -pass pass:"$PASS"
  rm -f "$ARCHIVE"
  ARCHIVE="$ENC"
  echo "backup encrypted ${TODAY} ${STAMP}" >> "$LOG"
else
  echo "backup WARN ${TODAY} no BACKUP_ENCRYPT_PASSPHRASE — plain tar.gz" >> "$LOG"
fi

if [ -f "$ARCHIVE" ]; then
  SIZE=$(du -h "$ARCHIVE" | cut -f1)
  echo "backup ok ${TODAY} ${STAMP} size=${SIZE} file=${ARCHIVE}" >> "$LOG"
else
  echo "backup FAILED ${STAMP}" >> "$LOG"
  exit 1
fi

find "$BK" -name 'agency-*.tar.gz*' -mtime +7 -delete 2>/dev/null || true
echo "===== backup done ${STAMP} =====" >> "$LOG"

if [ -x /root/app/scripts/backup_offsite.sh ]; then
  /bin/bash /root/app/scripts/backup_offsite.sh "$ARCHIVE" >> "$LOG" 2>&1 || true
fi

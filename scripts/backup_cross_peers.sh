#!/bin/bash
# Cross-Peer Backup web <-> auto (AES). Auf BEIDEN Hosts per Cron (unterschiedliche Richtung).
# ROLE=web  -> sichert lokale DB/Uploads, zieht n8n-Snapshot von auto (wenn PEER gesetzt)
# ROLE=auto -> sichert n8n data/.env, zieht orders.db-Snapshot von web
set -euo pipefail
LOG=/var/log/snack-cross-backup.log
BK=/root/app/backups/peer
STAMP=$(date +%Y%m%d_%H%M)
TODAY=$(date +%Y-%m-%d)
SECRETS=/root/app/deploy.secrets.local
ROLE="${BACKUP_PEER_ROLE:-}"
mkdir -p "$BK"

_read() {
  grep "^${1}=" "$SECRETS" 2>/dev/null | head -1 | cut -d= -f2- | sed 's/\r$//' | sed 's/^"//;s/"$//'
}

echo "===== cross-backup start $(date -Iseconds) role=${ROLE:-?} =====" >> "$LOG"

PASS="$(_read BACKUP_ENCRYPT_PASSPHRASE)"
if [ -z "$PASS" ]; then
  echo "cross-backup FAILED ${STAMP} no BACKUP_ENCRYPT_PASSPHRASE" >> "$LOG"
  exit 1
fi

# Lokales Bundle
LOCAL_LIST=()
if [ -f /root/app/backend/orders.db ]; then LOCAL_LIST+=(/root/app/backend/orders.db); fi
if [ -d /root/app/uploads ]; then LOCAL_LIST+=(/root/app/uploads); fi
if [ -d /opt/n8n ]; then
  [ -f /opt/n8n/.env ] && LOCAL_LIST+=(/opt/n8n/.env)
  [ -d /opt/n8n/data ] && LOCAL_LIST+=(/opt/n8n/data)
fi

if [ ${#LOCAL_LIST[@]} -eq 0 ]; then
  echo "cross-backup SKIP ${STAMP} nothing local" >> "$LOG"
  exit 0
fi

ARCHIVE="$BK/${ROLE:-host}-local-${STAMP}.tar.gz"
tar czf "$ARCHIVE" "${LOCAL_LIST[@]}" 2>>"$LOG"
ENC="${ARCHIVE}.enc"
openssl enc -aes-256-cbc -pbkdf2 -salt -in "$ARCHIVE" -out "$ENC" -pass pass:"$PASS"
rm -f "$ARCHIVE"
echo "cross-backup ok local ${TODAY} ${STAMP} file=${ENC}" >> "$LOG"

# Optional: Peer-Push via scp wenn Keys/Host gesetzt
PEER_HOST="$(_read BACKUP_PEER_HOST)"
PEER_USER="$(_read BACKUP_PEER_USER)"
if [ -n "$PEER_HOST" ] && [ -n "$PEER_USER" ] && [ -f "$ENC" ]; then
  REMOTE_DIR="$(_read BACKUP_PEER_PATH)"
  REMOTE_DIR="${REMOTE_DIR:-/root/app/backups/from-peer}"
  # sshpass optional; sonst erwartet eingerichteten SSH-Key
  SSH_OPTS="-o StrictHostKeyChecking=accept-new -o ConnectTimeout=12 -o ServerAliveInterval=5 -o ServerAliveCountMax=2"
  if command -v sshpass >/dev/null 2>&1; then
    PEER_PASS="$(_read BACKUP_PEER_PASSWORD)"
    if [ -z "$PEER_PASS" ]; then
      echo "cross-backup WARN peer-push skipped (no BACKUP_PEER_PASSWORD)" >> "$LOG"
    elif timeout 90 sshpass -p "$PEER_PASS" ssh $SSH_OPTS "${PEER_USER}@${PEER_HOST}" "mkdir -p ${REMOTE_DIR}" \
      && timeout 180 sshpass -p "$PEER_PASS" scp $SSH_OPTS "$ENC" "${PEER_USER}@${PEER_HOST}:${REMOTE_DIR}/"; then
      echo "cross-backup peer-push ok ${TODAY} -> ${PEER_HOST}" >> "$LOG"
    else
      echo "cross-backup WARN peer-push failed ${TODAY} -> ${PEER_HOST}" >> "$LOG"
    fi
  elif [ -f /root/.ssh/id_ed25519 ] || [ -f /root/.ssh/id_rsa ]; then
    if timeout 90 ssh $SSH_OPTS "${PEER_USER}@${PEER_HOST}" "mkdir -p ${REMOTE_DIR}" \
      && timeout 180 scp $SSH_OPTS "$ENC" "${PEER_USER}@${PEER_HOST}:${REMOTE_DIR}/"; then
      echo "cross-backup peer-push ok ${TODAY} -> ${PEER_HOST}" >> "$LOG"
    else
      echo "cross-backup WARN peer-push failed ${TODAY} -> ${PEER_HOST}" >> "$LOG"
    fi
  else
    echo "cross-backup WARN peer-push skipped (no sshpass/key)" >> "$LOG"
  fi
fi

find "$BK" -name '*.tar.gz.enc' -mtime +7 -delete 2>/dev/null || true
echo "===== cross-backup done ${STAMP} =====" >> "$LOG"

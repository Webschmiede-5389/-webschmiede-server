#!/bin/bash
# Off-Server-Backup: Hetzner Storage Box SFTP Port 23 via python3-paramiko
set -euo pipefail
LOG=/var/log/snack-backup.log
SECRETS=/root/app/deploy.secrets.local
ARCHIVE="${1:-}"

_read() {
  grep "^${1}=" "$SECRETS" 2>/dev/null | head -1 | cut -d= -f2- | sed 's/\r$//' | sed 's/^"//;s/"$//'
}

if [ ! -f "$SECRETS" ]; then
  echo "offsite skip $(date +%Y-%m-%d) no secrets" >> "$LOG"
  exit 0
fi

HOST="$(_read BACKUP_SFTP_HOST)"
USER="$(_read BACKUP_SFTP_USER)"
PASS="$(_read BACKUP_SFTP_PASS)"
RDIR="$(_read BACKUP_SFTP_PATH)"
PORT="$(_read BACKUP_SFTP_PORT)"
RDIR="${RDIR:-backups}"
PORT="${PORT:-23}"

if [ -z "$HOST" ] || [ -z "$USER" ] || [ -z "$PASS" ]; then
  echo "offsite skip $(date +%Y-%m-%d) not configured" >> "$LOG"
  exit 0
fi

if [ -z "$ARCHIVE" ] || [ ! -f "$ARCHIVE" ]; then
  ARCHIVE=$(ls -t /root/app/backups/daily/agency-*.tar.gz.enc /root/app/backups/daily/agency-*.tar.gz 2>/dev/null | head -1 || true)
fi
if [ -z "$ARCHIVE" ] || [ ! -f "$ARCHIVE" ]; then
  echo "offsite FAILED $(date +%Y-%m-%d) no archive" >> "$LOG"
  exit 1
fi

FNAME=$(basename "$ARCHIVE")
TODAY=$(date +%Y-%m-%d)

# System-Paket (kein pip break)
if ! python3 -c "import paramiko" 2>/dev/null; then
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-paramiko >/dev/null
fi

if python3 - "$HOST" "$PORT" "$USER" "$PASS" "$RDIR" "$ARCHIVE" "$FNAME" <<'PY' >>"$LOG" 2>&1
import sys
import paramiko

host, port, user, password, rdir, archive, fname = sys.argv[1:8]
port = int(port)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(
    hostname=host,
    port=port,
    username=user,
    password=password,
    look_for_keys=False,
    allow_agent=False,
    timeout=45,
)
sftp = client.open_sftp()
try:
    try:
        sftp.chdir(rdir)
    except IOError:
        try:
            sftp.mkdir(rdir)
            sftp.chdir(rdir)
        except Exception:
            pass
    sftp.put(archive, fname)
    print(f"paramiko put ok {fname}")
finally:
    sftp.close()
    client.close()
PY
then
  echo "offsite ok ${TODAY} file=${FNAME} host=${HOST}" >> "$LOG"
  exit 0
fi

echo "offsite FAILED ${TODAY} file=${FNAME} host=${HOST}" >> "$LOG"
exit 1

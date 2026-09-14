#!/usr/bin/env bash
#
# Backup der Schulplattform: PostgreSQL-Datenbank + hochgeladene Dateien.
# Für das docker-compose-Setup gedacht. Aufruf aus dem Projektordner:
#
#     ./scripts/backup.sh
#
# Aufbewahrung: alte Backups werden nach BACKUP_KEEP_DAYS Tagen gelöscht
# (Standard 30). Per Cron automatisierbar (siehe DEPLOY.md).

set -euo pipefail

# Ins Projektverzeichnis wechseln (ein Ordner über diesem Skript).
cd "$(dirname "$0")/.."

# .env laden (Datenbank-Zugangsdaten).
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
fi

DB_NAME="${DJANGO_DB_NAME:-schulplattform}"
DB_USER="${DJANGO_DB_USER:-schulplattform}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-30}"

# docker compose (v2) oder docker-compose (v1) erkennen.
if docker compose version >/dev/null 2>&1; then
    DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    DC="docker-compose"
else
    echo "Fehler: weder 'docker compose' noch 'docker-compose' gefunden." >&2
    exit 1
fi

TS="$(date +%Y%m%d-%H%M%S)"
DEST="backups/${TS}"
mkdir -p "${DEST}"

echo "→ Datenbank sichern (${DB_NAME}) ..."
$DC exec -T db pg_dump -U "${DB_USER}" "${DB_NAME}" | gzip > "${DEST}/db.sql.gz"

echo "→ Hochgeladene Dateien sichern ..."
$DC exec -T web tar czf - -C /app media > "${DEST}/media.tgz"

echo "→ Alte Backups (älter als ${KEEP_DAYS} Tage) entfernen ..."
find backups -mindepth 1 -maxdepth 1 -type d -mtime "+${KEEP_DAYS}" -exec rm -rf {} + 2>/dev/null || true

DB_SIZE="$(du -h "${DEST}/db.sql.gz" | cut -f1)"
MEDIA_SIZE="$(du -h "${DEST}/media.tgz" | cut -f1)"
echo "✓ Backup fertig: ${DEST} (DB ${DB_SIZE}, Dateien ${MEDIA_SIZE})"

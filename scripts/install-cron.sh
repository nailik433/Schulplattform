#!/usr/bin/env bash
#
# Richtet die automatische Wartung per Cron ein (einmal auf dem Server
# im Projektordner ausführen):
#
#     bash scripts/install-cron.sh
#
# - tägliches Backup (Datenbank + Uploads) um 2:30 Uhr  -> scripts/backup.sh
# - monatliches Löschen alter Abgaben (Löschkonzept)      -> purge_submissions
#
# Mehrfaches Ausführen ist unschädlich: bestehende Einträge werden ersetzt.

set -euo pipefail
cd "$(dirname "$0")/.."
DIR="$(pwd)"

BACKUP_LINE="30 2 * * * cd ${DIR} && ./scripts/backup.sh >> /var/log/schulplattform-backup.log 2>&1"
PURGE_LINE="0 3 1 * * cd ${DIR} && docker compose exec -T web python manage.py purge_submissions >> /var/log/schulplattform-purge.log 2>&1"

chmod +x scripts/backup.sh

{
    crontab -l 2>/dev/null | grep -v 'schulplattform-backup.log' | grep -v 'schulplattform-purge.log' || true
    echo "${BACKUP_LINE}"
    echo "${PURGE_LINE}"
} | crontab -

echo "✓ Cron eingerichtet:"
echo "  - tägliches Backup um 2:30 Uhr      (Log: /var/log/schulplattform-backup.log)"
echo "  - monatliches Löschen alter Abgaben (Log: /var/log/schulplattform-purge.log)"
echo
echo "Aktuelle Einträge:"
crontab -l | grep schulplattform || true

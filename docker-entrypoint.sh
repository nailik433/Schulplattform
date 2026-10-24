#!/bin/sh
# Prepare the app on container start, then hand off to the given command
# (gunicorn by default). Safe to run on every deploy: migrations and
# collectstatic are idempotent.
set -e

echo "→ Datenbank-Migrationen anwenden ..."
python manage.py migrate --no-input

echo "→ Statische Dateien sammeln ..."
python manage.py collectstatic --no-input

exec "$@"

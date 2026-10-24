#!/usr/bin/env bash
#
# Update der laufenden Plattform auf die neueste Version.
# Auf dem Server im Projektordner ausführen:
#
#     bash scripts/update.sh
#
# Holt den neuesten Code und baut die Container neu. Migrationen und das
# Sammeln statischer Dateien laufen beim Start automatisch.

set -euo pipefail
cd "$(dirname "$0")/.."

OLD="$(git rev-parse HEAD)"
echo "→ Neuesten Code holen ..."
git pull
NEW="$(git rev-parse HEAD)"

echo "→ Neu bauen und starten ..."
docker compose up -d --build

# Caddy liest die Caddyfile nur beim Start: bei Änderung neu starten.
if ! git diff --quiet "$OLD" "$NEW" -- Caddyfile; then
    echo "→ Caddyfile geändert – Caddy neu starten ..."
    docker compose restart caddy
fi

echo "✓ Update eingespielt."

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

echo "→ Neuesten Code holen ..."
git pull

echo "→ Neu bauen und starten ..."
docker compose up -d --build

echo "✓ Update eingespielt."

#!/usr/bin/env bash
#
# Einmalige Server-Einrichtung der Schulplattform.
# Auf dem frisch gemieteten Server (im Projektordner) EINMAL ausführen:
#
#     bash scripts/server-setup.sh
#
# Das Skript installiert Docker, richtet die Firewall ein, fragt Domain +
# E-Mail ab, erzeugt sichere Schlüssel/Passwörter, schreibt die .env und
# startet die Plattform. Danach nur noch ein Admin-Konto anlegen.

set -euo pipefail
cd "$(dirname "$0")/.."

echo "== Schulplattform – Server-Einrichtung =="

# 1. Docker installieren (falls nicht vorhanden)
if ! command -v docker >/dev/null 2>&1; then
    echo "→ Docker installieren ..."
    curl -fsSL https://get.docker.com | sh
else
    echo "→ Docker ist bereits installiert."
fi

# 2. Firewall (nur SSH + Web), best effort
if command -v ufw >/dev/null 2>&1; then
    echo "→ Firewall einrichten ..."
    ufw allow OpenSSH >/dev/null 2>&1 || true
    ufw allow 80 >/dev/null 2>&1 || true
    ufw allow 443 >/dev/null 2>&1 || true
    ufw --force enable >/dev/null 2>&1 || true
fi

# 3. .env erzeugen (falls noch nicht vorhanden)
if [ -f .env ]; then
    echo "→ .env existiert bereits – wird nicht überschrieben."
else
    echo
    read -rp "Deine Domain (z. B. schule.example.de): " DOMAIN
    read -rp "Deine E-Mail (für das HTTPS-Zertifikat):   " EMAIL

    gen() { python3 -c "import secrets;print(secrets.token_urlsafe($1))" 2>/dev/null \
            || openssl rand -base64 "$1" | tr -d '\n/+='; }
    SECRET="$(gen 50)"
    DBPW="$(gen 24)"

    cat > .env <<ENV
DJANGO_SECRET_KEY=${SECRET}
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=${DOMAIN}
DJANGO_CSRF_TRUSTED_ORIGINS=https://${DOMAIN}
DJANGO_SITE_URL=https://${DOMAIN}

DJANGO_DB_NAME=schulplattform
DJANGO_DB_USER=schulplattform
DJANGO_DB_PASSWORD=${DBPW}

DOMAIN=${DOMAIN}
LETSENCRYPT_EMAIL=${EMAIL}
ENV
    echo "→ .env erstellt."
fi

# 4. Starten
echo "→ Plattform bauen und starten (das dauert beim ersten Mal ein paar Minuten) ..."
docker compose up -d --build

echo
echo "✓ Fertig! Sobald das HTTPS-Zertifikat geholt ist (ein paar Sekunden),"
echo "  ist die Plattform unter deiner Domain erreichbar."
echo
echo "  Jetzt noch dein Admin-Konto anlegen:"
echo "    docker compose exec web python manage.py createsuperuser"

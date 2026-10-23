#!/usr/bin/env bash
#
# Richtet den E-Mail-Versand (SMTP) ein. Danach werden Passwort-Zurücksetzen-
# und Einladungs-Mails wirklich verschickt statt nur ins Server-Log geschrieben.
# Auf dem Server im Projektordner ausführen:
#
#     bash scripts/configure-email.sh
#
# Die Zugangsdaten bekommst du von deinem E-Mail-Anbieter
# (z. B. IONOS: smtp.ionos.de, Port 587, Benutzer = deine E-Mail-Adresse).

set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
    echo "Keine .env gefunden – bitte zuerst scripts/server-setup.sh ausführen." >&2
    exit 1
fi

echo "== Schulplattform – E-Mail-Versand (SMTP) einrichten =="
read -rp "SMTP-Server (z. B. smtp.ionos.de):            " HOST
read -rp "Port [587]:                                    " PORT
PORT="${PORT:-587}"
read -rp "Benutzername (meist deine E-Mail-Adresse):     " USER_
read -rsp "Passwort (Eingabe bleibt unsichtbar):          " PASS
echo
read -rp "Absender-Adresse [${USER_}]:                   " FROM
FROM="${FROM:-$USER_}"

# Alte E-Mail-Einträge entfernen, neue anhängen.
grep -v -e '^DJANGO_EMAIL_' -e '^DJANGO_DEFAULT_FROM_EMAIL' .env > .env.tmp || true
mv .env.tmp .env
cat >> .env <<ENV
DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DJANGO_EMAIL_HOST=${HOST}
DJANGO_EMAIL_PORT=${PORT}
DJANGO_EMAIL_HOST_USER=${USER_}
DJANGO_EMAIL_HOST_PASSWORD=${PASS}
DJANGO_EMAIL_USE_TLS=true
DJANGO_DEFAULT_FROM_EMAIL=Schulplattform <${FROM}>
ENV
echo "→ .env aktualisiert. Web-Container mit neuen Einstellungen starten ..."
docker compose up -d web >/dev/null

read -rp "Empfänger für eine Test-Mail (Enter = überspringen): " TO
if [ -n "${TO}" ]; then
    if docker compose exec -T web python manage.py sendtestemail "${TO}"; then
        echo "✓ Test-Mail an ${TO} geschickt – bitte Posteingang prüfen (auch Spam-Ordner)."
    else
        echo "✗ Versand fehlgeschlagen. Zugangsdaten prüfen; Details: docker compose logs web | tail" >&2
    fi
fi
echo "✓ E-Mail-Versand eingerichtet."

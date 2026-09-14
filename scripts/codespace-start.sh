#!/usr/bin/env bash
#
# Ein-Klick-Start für den Test im GitHub Codespace:
#   bash scripts/codespace-start.sh
#
# Installiert Abhängigkeiten, richtet die Datenbank ein, legt einen Test-Admin
# an (nur im Entwicklungsmodus) und startet den Server.
#
# NUR zum Testen. Der Test-Admin wird nur angelegt, wenn DEBUG aktiv ist –
# auf einem echten Server (DEBUG=false) passiert das nicht.

set -e
cd "$(dirname "$0")/.."

echo "→ 1/4 Bausteine installieren ..."
pip install -q -r requirements.txt

echo "→ 2/4 Datenbank einrichten ..."
python manage.py migrate

echo "→ 3/4 Test-Admin sicherstellen ..."
python manage.py shell -c "
from django.conf import settings
from django.contrib.auth import get_user_model
U = get_user_model()
email = 'admin@demo.de'
if settings.DEBUG and not U.objects.filter(email=email).exists():
    U.objects.create_superuser(email=email, password='demo12345')
    print('   Test-Admin angelegt  →  E-Mail: admin@demo.de   Passwort: demo12345')
elif U.objects.filter(email=email).exists():
    print('   Test-Admin existiert bereits (admin@demo.de / demo12345)')
else:
    print('   Kein Test-Admin (nur im Entwicklungsmodus).')
"

echo "→ 4/4 Server starten ... (offen lassen; Stoppen mit Strg+C)"
echo "   Wenn 'Open in Browser' erscheint: anklicken."
python manage.py runserver 0.0.0.0:8000

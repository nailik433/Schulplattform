# Schulplattform

Eine Online-Plattform, mit der Lehrkräfte Klassen verwalten, digitale
Arbeitsblätter austeilen und Abgaben ihrer Schüler/innen einsammeln können –
für die Nutzung von der Schule **und** von zu Hause. Läuft komplett auf einem
eigenen (gemieteten) Server, z. B. bei Hostinger.

Schüler/innen melden sich **ohne E-Mail und ohne Passwort** an – nur mit einem
persönlichen, zufälligen **Zugangscode**, den die Lehrkraft erzeugt.

---

## Was schon funktioniert (MVP – Stufe 1)

- **Lehrer-Konto**: Registrierung und Login per E-Mail-Adresse.
- **Schulen anlegen** und darunter **Klassen** (z. B. „5a – Informatik“).
- **Schüler/innen hinzufügen** – einzeln oder mehrere auf einmal (eine Zeile
  pro Name). Für jede/n wird automatisch ein eindeutiger 8-stelliger
  Zugangscode erzeugt.
- **Zugangscodes verwalten**: neu erzeugen, Schüler/in deaktivieren/aktivieren,
  entfernen.
- **Schüler-Login** nur mit Zugangscode; eigene Startseite pro Schüler/in.
- **Zugriffsschutz**: Eine Lehrkraft sieht ausschließlich ihre eigenen Klassen.
  Das Datenmodell ist bereits auf das spätere Teilen mit Kolleg/innen
  vorbereitet (Rollen `Inhaber` / `Kollege/Kollegin` pro Klasse), sodass
  geteilte Kolleg/innen nur auf die freigegebene Klasse zugreifen – nie auf
  die übrigen Kurse.
- **Admin-Bereich** (`/admin/`) für die technische Verwaltung.

## Nächste Ausbaustufen (geplant)

- **Stufe 2** – Arbeitsblätter/Dateien an eine Klasse austeilen.
- **Stufe 3** – Abgaben einsammeln (Datei-Upload durch Schüler/innen),
  Abgabe-Übersicht und Fristen.
- **Stufe 4** – Klasse an Kolleg/innen weiterleiten (Freigabe-UI auf Basis des
  bereits vorhandenen Rollenmodells).

---

## Technologie

- **Python 3.11+ / Django 5.1** – Backend, Auth, Datenbank-ORM und ein fertiger
  Admin-Bereich.
- **SQLite** für die lokale Entwicklung, **PostgreSQL** für den Produktivbetrieb
  (per Umgebungsvariablen umschaltbar, kein Code-Änderung nötig).
- Server-gerendertes HTML mit schlankem CSS (keine Frontend-Build-Kette nötig –
  läuft daher auf sehr einfachem Hosting).

**Warum Django?** Die Anforderungen (Nutzerkonten, Rollen/Rechte, viel
Verwaltung von Klassen und Schüler/innen, Datei-Uploads) deckt Django von Haus
aus ab. Der mitgelieferte Admin-Bereich spart viel Verwaltungs-Code, und ein
Django-Projekt lässt sich auf praktisch jedem gemieteten Linux-Server (inkl.
Hostinger VPS) mit Gunicorn + Nginx betreiben.

---

## Lokale Einrichtung

```bash
# 1. Virtuelle Umgebung anlegen und Abhängigkeiten installieren
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Datenbank vorbereiten
python manage.py migrate

# 3. Admin-Zugang anlegen (optional, für /admin/)
python manage.py createsuperuser

# 4. Entwicklungsserver starten
python manage.py runserver
```

Dann im Browser: <http://127.0.0.1:8000/>

- Lehrer-Konto anlegen: **Lehrer-Konto erstellen**
- Danach: Schule anlegen → Klasse anlegen → Schüler/innen hinzufügen
- Schüler-Login testen: <http://127.0.0.1:8000/s/anmelden/>

### Tests

```bash
python manage.py test
```

---

## Betrieb auf einem eigenen Server (Kurzfassung)

Die produktionsrelevanten Einstellungen werden über Umgebungsvariablen
gesteuert – Vorlage siehe [`.env.example`](.env.example).

1. **Abhängigkeiten**: in `requirements.txt` die auskommentierten Produktions-
   Pakete aktivieren (`gunicorn`, `psycopg[binary]`, `whitenoise`).
2. **`.env` befüllen**: sicheren `DJANGO_SECRET_KEY` setzen, `DJANGO_DEBUG=false`,
   deine Domain in `DJANGO_ALLOWED_HOSTS` und `DJANGO_CSRF_TRUSTED_ORIGINS`,
   sowie die PostgreSQL-Zugangsdaten.
3. **Datenbank & statische Dateien**:
   ```bash
   python manage.py migrate
   python manage.py collectstatic --no-input
   ```
4. **App-Server**: `gunicorn config.wsgi:application` hinter einem Reverse Proxy
   (Nginx), TLS-Zertifikat z. B. via Let's Encrypt.
5. Bei `DJANGO_DEBUG=false` schaltet die App automatisch HTTPS-Erzwingung,
   sichere Cookies und HSTS ein.

---

## Datenschutz (DSGVO)

Es werden personenbezogene Daten von Minderjährigen verarbeitet. Vor einem
echten Einsatz an einer Schule sind u. a. zu klären: Rechtsgrundlage/Einwilligung,
Auftragsverarbeitung, Serverstandort (EU), Löschkonzept und Freigabe durch die
Schulleitung bzw. den/die Datenschutzbeauftragte/n. Die Plattform speichert
bewusst so wenig wie möglich – von Schüler/innen nur einen Anzeigenamen und den
Zugangscode, keine E-Mail-Adressen oder Passwörter.

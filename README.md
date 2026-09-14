# Schulplattform

Eine Online-Plattform, mit der Lehrkräfte Klassen verwalten, digitale
Arbeitsblätter austeilen und Abgaben ihrer Schüler/innen einsammeln können –
für die Nutzung von der Schule **und** von zu Hause. Läuft komplett auf einem
eigenen (gemieteten) Server, z. B. bei Hostinger.

Schüler/innen melden sich **ohne E-Mail und ohne Passwort** an – nur mit einem
persönlichen, zufälligen **Zugangscode**, den die Lehrkraft erzeugt.

---

## Was schon funktioniert

**Zugang & Verwaltung**

- **Schulen** legt ausschließlich der/die Plattform-Betreiber/in im
  **Admin-Bereich** (`/admin/`) an. Lehrkräfte können keine Schulen erstellen.
- **Lehrkräfte registrieren sich nicht frei**, sondern gelangen auf zwei Wegen
  zu einem Konto – jeweils fest einer Schule zugeordnet:
  - **Einladung**: Der Betreiber erstellt im Admin eine Einladung (E-Mail +
    Schule); die Lehrkraft öffnet den Einladungslink, setzt Name + Passwort –
    fertig. Der Link wird im Admin angezeigt (zum Weitergeben) und, falls
    E-Mail konfiguriert ist, automatisch verschickt.
  - **Anfrage**: Die Lehrkraft stellt über `/konto/anfrage/` eine Beitritts-
    anfrage zu einer Schule. Der Betreiber genehmigt sie im Admin – dabei wird
    automatisch eine Einladung erzeugt.
- **Login** per E-Mail-Adresse und Passwort.

**Klassen & Schüler/innen**

- **Klassen** (z. B. „5a – Informatik“) legt die Lehrkraft in **ihrer** Schule an.
- **Schüler/innen anlegen** auf drei Wegen: als Anzahl anonymer Plätze
  (#001, #002 …), einzeln mit optionalem Namen, oder als Namensliste. Jede/r
  bekommt automatisch eine fortlaufende Nummer und einen eindeutigen
  **8-stelligen Token** (Kleinbuchstaben + Ziffern, ohne verwechselbare Zeichen).
- **Tokens verwalten**: neu erzeugen, deaktivieren/aktivieren, entfernen.
- **Schüler-Login** ohne Konto – nur per Token: entweder auf der Startseite
  (`/s/`) eintippen oder den **QR-Code scannen**, der direkt auf `/s/<token>/`
  führt und einloggt. Ein Brute-Force-Schutz begrenzt Fehlversuche pro IP.
- **QR-Druckdokument** pro Klasse (`🖨️`): A4-Seiten mit QR-Karten im
  3×5-Raster zum Ausschneiden plus eine vertrauliche Lehrerliste für die
  handschriftliche Namenszuordnung. Die QR-Codes werden **lokal auf dem
  Server** erzeugt – die Tokens verlassen den Server nicht.
- **Zugriffsschutz**: Eine Lehrkraft sieht ausschließlich ihre eigenen Klassen.
  Das Datenmodell ist bereits auf das spätere Teilen mit Kolleg/innen
  vorbereitet (Rollen `Inhaber` / `Kollege/Kollegin` pro Klasse), sodass
  geteilte Kolleg/innen nur auf die freigegebene Klasse zugreifen – nie auf
  die übrigen Kurse.

**Arbeitsblätter austeilen**

- Eine Lehrkraft legt in einer Klasse **Arbeitsblätter** an (Titel,
  Beschreibung, optionale Frist) und hängt **eine oder mehrere Dateien** an
  (z. B. PDFs, max. 25 MB/Datei).
- **Schüler/innen** sehen die Arbeitsblätter nach dem Login auf ihrer
  Startseite und können die Dateien herunterladen.
- **Geschützte Downloads**: Dateien werden nicht über öffentliche URLs
  ausgeliefert, sondern nur über eine zugriffsgeprüfte View – erreichbar für
  die Lehrkräfte der Klasse und deren Schüler/innen, sonst nicht.

**Abgaben einsammeln**

- Pro Arbeitsblatt lässt sich das Einsammeln von **Abgaben** aktivieren
  (Standard) oder abschalten (reines Material).
- **Schüler/innen** laden ihre Lösung(en) direkt auf ihrer Startseite hoch,
  sehen ihre eigenen Dateien und können sie wieder entfernen. Abgaben nach der
  Frist werden als **verspätet** markiert.
- **Lehrkräfte** sehen je Arbeitsblatt eine **Abgabe-Übersicht** (wer hat
  abgegeben, wann, verspätet?) und laden die abgegebenen Dateien herunter.
- **Vertraulichkeit**: Abgabe-Dateien sind nur für die Lehrkräfte der Klasse
  und die jeweils abgebende Person zugänglich – kein/e Schüler/in sieht die
  Abgaben anderer.

**Erste Schritte als Betreiber:** nach `createsuperuser` im Admin (`/admin/`)
zuerst eine oder mehrere **Schulen** anlegen, dann Lehrkräfte per **Einladung**
einladen oder eingegangene **Zugangsanfragen** genehmigen.

## Nächste Ausbaustufen (geplant)

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

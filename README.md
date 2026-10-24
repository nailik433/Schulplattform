# Schulplattform

Eine selbst gehostete Plattform für den Unterricht: Lehrkräfte verwalten
Klassen, teilen digitale **Arbeitsblätter** aus, sammeln **Abgaben** ein und
stellen **interaktive Lernumgebungen** bereit – von Claude direkt in die
Klasse geschrieben. Schüler/innen melden sich **ohne Konto** an, nur mit einem
6-stelligen Zugangscode oder per QR-Code.

Läuft komplett auf einem eigenen, gemieteten Server (Docker + automatisches
HTTPS), z. B. bei Hetzner. Live-Instanz: `https://hebid.de`.

---

## Was die Plattform kann

**Schüler/innen (iPad & Smartphone zuerst)**
- Anmeldung per **6-stelligem Code** oder **QR-Scan** – kein Name, keine
  E-Mail, kein Passwort. Anonyme Kennungen wie `7b-001`.
- Startseite **„Meine Aufgaben"** mit klarem Status: offen · bald fällig ·
  Frist vorbei · abgegeben; Lernumgebungen mit erledigt/Punkten.
- **Lernumgebungen** bildschirmfüllend öffnen (interaktive HTML-Seiten mit
  Animationen und Aufgaben, isoliert in einer Sandbox).
- Abgaben **hochladen** – auch direkt als Foto vom Handy.
- Sitzung endet automatisch mit dem Schultag (geteilte iPads).

**Lehrkräfte**
- Login per E-Mail + Passwort (mit Brute-Force-Schutz), Passwort-Reset per
  E-Mail. Konten nur per **Einladung** oder genehmigter **Zugangsanfrage**,
  fest einer Schule zugeordnet.
- **Klassen** anlegen; Schüler/innen als anonyme Plätze, als Namensliste oder
  per **Import** bestehender Tokens (z. B. zwei Excel-Spalten aus Fobizz).
  Tokens neu erzeugen, ändern, deaktivieren; Mehrfach-Löschen; Klasse nur mit
  getippter Bestätigung löschen.
- **QR-Druckdokument** (A4, bis 31 Karten pro Seite) + vertrauliche
  Lehrerliste zur handschriftlichen Namenszuordnung.
- **Arbeitsblätter** austeilen (Drag & Drop oder Dateiauswahl, Frist,
  Abgaben ein/aus); Abgabe-Übersicht mit „verspätet"-Markierung.
- **Alle Abgaben als ZIP** herunterladen – pro Schüler/in ein Ordner
  (`7b-001/…`), ideal für die KI-gestützte Bewertung.
- **Lernumgebungen** anlegen (HTML einfügen oder per API) mit
  Ergebnis-Übersicht pro Schüler/in (Status, Punkte, Prozent).
- **Klassen mit Kolleg/innen teilen**: Kolleg/innen sehen nur die geteilte
  Klasse, nie die anderen Kurse.
- **Mein Material**: private Dateiablage pro Lehrkraft mit beliebig verschachtelten
  Ordnern (Drag & Drop, umbenennen, verschieben, löschen). Beim Austeilen eines
  Arbeitsblatts oder im Projekt wählst du Dateien direkt daraus aus – sie werden
  kopiert, spätere Änderungen im Material betreffen ausgeteilte Blätter nicht.
- **Projekte**: Vorlagen aus Bausteinen (Lernumgebung, Arbeitsblatt, **Arbeitsauftrag**
  nur mit Abgabe, z. B. „Erstelle eine Präsentation“), die du in beliebig vielen
  Klassen einsetzt. Schüler/innen sehen ein Projekt als gebündelte Karte mit
  Fortschritt („2 von 3 erledigt“).

**KI-Schnittstelle („Weg B": Cowork / Claude Code)**
- Jede Lehrkraft hat einen **API-Schlüssel** (Dashboard → „KI & API").
- `GET /api/classes` · `POST /api/lessons` – Claude baut die Lernumgebung
  und legt sie **direkt in der richtigen Klasse** ab.
- **Eingebauter MCP-Server** (`/mcp`): als *Custom Connector* in Cowork /
  claude.ai hinzufügen – fertige Werkzeuge ohne Installation
  ([`mcp/README.md`](mcp/README.md)). Zusätzlich ein lokaler Connector für
  Claude Code / Desktop und das [`docs/COWORK-BRIEFING.md`](docs/COWORK-BRIEFING.md)
  für den reinen API-Weg.
- **Lernfortschritt pro Klasse**: Matrix Schüler × Lernumgebungen/Abgaben,
  CSV-Export für Excel.
- **Dark Mode** folgt der Systemeinstellung.

**Betrieb & Datenschutz**
- Docker Compose (Gunicorn + PostgreSQL + Caddy mit Let's-Encrypt-HTTPS),
  WhiteNoise für statische Dateien, Uploads nur über zugriffsgeprüfte Views.
- Setup-, Update-, Backup- und Cron-Skripte in [`scripts/`](scripts/);
  **Auto-Deploy** per GitHub Actions ([`docs/AUTO-DEPLOY.md`](docs/AUTO-DEPLOY.md)).
- Löschkonzept (`purge_submissions`), Impressum/Datenschutz-Vorlagen,
  Datensparsamkeit (von Schüler/innen nur Nummer + Zugangscode).

---

## Sicherheitskonzept (Kurzfassung)

- **Lernumgebungs-HTML ist fremder Code.** Es wird mit
  `Content-Security-Policy: sandbox` ausgeliefert und nur in sandboxed
  iframes eingebettet – es läuft immer mit opaker Origin und kann weder
  Cookies lesen noch als Lehrkraft handeln, auch wenn man es direkt öffnet.
- **Token nie in der URL halten:** Der QR-Link `/s/<token>/` loggt ein und
  leitet sofort auf `/start/` um.
- **Brute-Force-Schutz** für Schüler-Code *und* Lehrer-Login (pro IP bzw.
  pro IP + E-Mail, serverweit über einen geteilten Cache); `X-Forwarded-For`
  wird nur in der vom Proxy gesetzten Form vertraut.
- Produktion startet **nicht ohne gesetzten `DJANGO_SECRET_KEY`**; HSTS,
  sichere Cookies, SSL-Redirect, `X-Frame-Options: DENY` (außer für die
  eigenen Lernumgebungs-Frames: `SAMEORIGIN`).
- Upload-Limit pro Datei (25 MB) in der App und pro Request am Proxy.

---

## Technologie

- **Python 3.11+ / Django 5.1** – Backend, Auth, ORM, Admin.
- **SQLite** lokal, **PostgreSQL** in Produktion (per Umgebungsvariablen).
- Server-gerendertes HTML + schlankes CSS (Apple-artiges, ruhiges Design,
  iPad-optimiert) – keine Frontend-Build-Kette.

---

## Lokale Einrichtung

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser        # für /admin/
python manage.py runserver
```

Dann <http://127.0.0.1:8000/>: Im Admin eine **Schule** anlegen und dich ihr
zuordnen → Klasse anlegen → Schüler/innen hinzufügen → QR-Dokument drucken.
Schüler-Login testen unter <http://127.0.0.1:8000/s/>.

Tests:

```bash
python manage.py test
```

---

## Betrieb auf dem eigenen Server

Schritt für Schritt in [`docs/SERVER-HETZNER.md`](docs/SERVER-HETZNER.md).
Kurz: Server + Domain → `git clone` → `bash scripts/server-setup.sh` →
`createsuperuser` → `bash scripts/install-cron.sh`. Updates danach über das
Auto-Deploy (oder `bash scripts/update.sh`).

Arbeitsplan für die nächsten Schritte: [`docs/NAECHSTE-SCHRITTE.md`](docs/NAECHSTE-SCHRITTE.md).

---

## Datenschutz (DSGVO)

Es werden Daten von Minderjährigen verarbeitet. Vor dem Einsatz an einer
Schule sind u. a. zu klären: Rechtsgrundlage, Auftragsverarbeitung,
Serverstandort (EU), Löschkonzept und die Freigabe durch Schulleitung bzw.
Datenschutzbeauftragte/n. Die Plattform speichert bewusst so wenig wie
möglich – von Schüler/innen standardmäßig nur eine Nummer und den Zugangscode.

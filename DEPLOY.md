# Testen & Live schalten

Zwei Wege, je nach Ziel:

- **A) Beta testen – ganz ohne eigenen Server** (GitHub Codespaces oder ein
  kostenloser Hosting-Dienst)
- **B) Produktiv betreiben** auf einem gemieteten Server (z. B. Hostinger VPS)

---

## A) Beta testen ohne eigenen Server

### Variante 1: GitHub Codespaces (empfohlen für den schnellen Test)

Codespaces ist GitHubs Cloud-Umgebung. Die App läuft dort und ist über eine
temporäre öffentliche URL erreichbar – auch für Kolleg/innen. Für persönliche
Konten gibt es ein kostenloses Monatskontingent.

> ℹ️ **GitHub Pages geht nicht** – das kann nur statische Seiten, kein Django
> und keine Datenbank.

**So geht's:**

1. Auf GitHub im Repo auf **Code → Codespaces → Create codespace on
   `claude/school-platform-worksheets-c0x6aj`** klicken.
2. Warten, bis die Einrichtung durchläuft (installiert automatisch alle
   Pakete und legt die Datenbank an – konfiguriert in
   `.devcontainer/devcontainer.json`).
3. Im Terminal des Codespace den Server starten:
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```
4. Codespaces bietet automatisch die weitergeleitete URL an (Tab **Ports**).
   Damit auch andere testen können: im Reiter **Ports** bei Port 8000 mit
   Rechtsklick **Port Visibility → Public** wählen.
5. Fertig – die öffentliche URL im Browser öffnen. `*.app.github.dev` wird
   von der App automatisch akzeptiert (in `settings.py` bereits vorbereitet).

Optional ein Admin-Login anlegen:
```bash
python manage.py createsuperuser
```

> Hinweis: Das ist eine Test-Umgebung mit SQLite. Daten bleiben nur so lange
> erhalten, wie der Codespace besteht. Für einen echten Beta-Betrieb mit
> mehreren Nutzern über Wochen ist Variante 2 oder B besser.

### Variante 2: Kostenloser Hosting-Dienst, direkt aus GitHub

Dienste wie **Render**, **Railway** oder **Fly.io** deployen direkt aus dem
GitHub-Repo – ohne dass du einen Server mietest oder verwaltest. Sie bieten
kostenlose Einstiegs-Tarife (mit Einschränkungen, z. B. schläft die App bei
Inaktivität ein).

Grobes Vorgehen am Beispiel Render:

1. Konto bei Render anlegen und GitHub verbinden.
2. **New → Web Service**, dieses Repo wählen.
3. Build Command: `pip install -r requirements.txt`
   Start Command: `./docker-entrypoint.sh gunicorn config.wsgi:application`
4. Eine kostenlose **PostgreSQL**-Datenbank anlegen und deren Zugangsdaten als
   Environment-Variablen setzen (`DJANGO_DB_*`), dazu `DJANGO_SECRET_KEY`,
   `DJANGO_DEBUG=false`, `DJANGO_ALLOWED_HOSTS` = die von Render vergebene
   Domain und `DJANGO_CSRF_TRUSTED_ORIGINS=https://<deine-render-domain>`.

Damit bekommst du eine dauerhafte Test-URL, ohne eigenen Server.

---

## B) Produktiv auf einem gemieteten Server (Docker)

Für den echten Betrieb inkl. eigener Domain und automatischem HTTPS liegt ein
fertiges Docker-Setup bei: **Django (Gunicorn) + PostgreSQL + Caddy**. Caddy
holt und erneuert das HTTPS-Zertifikat automatisch.

**Voraussetzungen:** ein Linux-Server mit Docker (ein Hostinger **VPS**, nicht
das reine Webhosting-Paket), eine Domain, deren DNS-A-Eintrag auf die Server-IP
zeigt.

```bash
# 1. Code auf den Server bringen (zwei Möglichkeiten, siehe unten)

# 2. Konfiguration anlegen und ausfüllen
cp .env.example .env
nano .env      # SECRET_KEY, Passwörter, DOMAIN, LETSENCRYPT_EMAIL, SITE_URL ...

# 3. Starten (baut Images, migriert DB, sammelt static, startet alles)
docker compose up -d --build

# 4. Admin-Konto anlegen
docker compose exec web python manage.py createsuperuser
```

Danach ist die Plattform unter `https://<DOMAIN>` erreichbar. Melde dich unter
`https://<DOMAIN>/admin/` an und lege dort zuerst die **Schulen** an; danach
kannst du Lehrkräfte per Einladung einladen oder Zugangsanfragen genehmigen.

### Code auf den Server bringen – mit oder ohne GitHub

Das Setup braucht nur die Projektdateien, **kein GitHub**. Zwei Wege:

**Weg 1 – ohne GitHub (Archiv hochladen).** Auf deinem PC ein Archiv des
Projekts erzeugen und per SCP auf den Server kopieren:

```bash
# auf deinem Rechner, im Projektordner:
tar --exclude='.git' --exclude='.venv' --exclude='db.sqlite3' \
    --exclude='staticfiles' --exclude='media' -czf schulplattform.tar.gz .
scp schulplattform.tar.gz benutzer@SERVER-IP:~/

# auf dem Server:
mkdir -p schulplattform && tar -xzf schulplattform.tar.gz -C schulplattform
cd schulplattform
```

Für spätere Updates einfach ein neues Archiv hochladen, entpacken und erneut
`docker compose up -d --build` ausführen.

**Weg 2 – mit git** (auch von einem eigenen/privaten Git-Server möglich, nicht
nur GitHub):

```bash
git clone <REPO-URL> schulplattform && cd schulplattform
```

**Updates einspielen:**
```bash
git pull
docker compose up -d --build
```
Migrationen und das Sammeln der statischen Dateien laufen dabei automatisch
über `docker-entrypoint.sh`.

### Ohne Docker (klassisch)

Alternativ direkt mit `gunicorn config.wsgi:application` hinter Nginx +
Certbot; PostgreSQL separat. Die nötigen Umgebungsvariablen sind dieselben
(siehe `.env.example`), `python manage.py migrate` und `collectstatic` müssen
dann manuell laufen.

---

## Datenschutz-Hinweis

Vor einem echten Einsatz an einer Schule die DSGVO-Punkte klären (siehe
Abschnitt „Datenschutz" in der `README.md`): Einwilligung, EU-Serverstandort,
Löschkonzept, Freigabe durch die Schule.

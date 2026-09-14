# Live gehen: Schritt-für-Schritt (Hetzner VPS)

Diese Anleitung bringt die Schulplattform auf einen eigenen, gemieteten Server
mit eigener Domain und automatischem HTTPS. Sie ist für Hetzner geschrieben,
funktioniert aber praktisch identisch bei **Netcup, IONOS oder einem Hostinger
VPS** – überall dort, wo du einen Ubuntu-Server mit Root-Zugang bekommst.

Zeitaufwand: ca. 30–60 Minuten. Du brauchst: eine Kreditkarte/PayPal für den
Server, einen Domainnamen und ein Terminal (Mac/Linux: „Terminal"; Windows:
„PowerShell" oder „Windows Terminal").

---

## 1. Server bestellen

1. Konto bei <https://www.hetzner.com/cloud> anlegen.
2. **New Project** → **Add Server**.
3. **Location:** Deutschland (Nürnberg oder Falkenstein) – wichtig für den
   Datenschutz.
4. **Image:** Ubuntu 24.04.
5. **Type:** CX22 (2 vCPU, 4 GB RAM) reicht für den Anfang (~5 €/Monat).
6. **SSH Key** hinterlegen (empfohlen) oder Passwort per E-Mail nutzen.
7. Server erstellen. Notiere dir die **IP-Adresse** (z. B. `203.0.113.10`).

## 2. Domain verbinden (DNS)

Bei deinem Domain-Anbieter einen **A-Record** setzen:

| Typ | Name | Wert |
|-----|------|------|
| A   | `@` (oder Subdomain, z. B. `schule`) | die Server-IP |

Bis das weltweit greift, können ein paar Minuten bis Stunden vergehen.
Prüfen: `ping deine-domain.de` sollte die Server-IP zeigen.

## 3. Per SSH einloggen

```bash
ssh root@DEINE-SERVER-IP
```

Beim ersten Mal „yes" bestätigen. Dann System aktualisieren:

```bash
apt update && apt upgrade -y
```

## 4. Firewall & Docker

```bash
# Firewall: nur SSH + Web erlauben
apt install -y ufw
ufw allow OpenSSH
ufw allow 80
ufw allow 443
ufw --force enable

# Docker installieren
curl -fsSL https://get.docker.com | sh
```

Test: `docker compose version` sollte eine Version anzeigen.

## 5. Code auf den Server bringen

**Variante A – ohne GitHub (Archiv hochladen).** Auf deinem eigenen Rechner im
Projektordner:

```bash
tar --exclude='.git' --exclude='.venv' --exclude='db.sqlite3' \
    --exclude='staticfiles' --exclude='media' --exclude='backups' \
    -czf schulplattform.tar.gz .
scp schulplattform.tar.gz root@DEINE-SERVER-IP:~/
```

Dann auf dem Server:

```bash
mkdir -p schulplattform && tar -xzf schulplattform.tar.gz -C schulplattform
cd schulplattform
```

**Variante B – mit git:** `git clone <REPO-URL> schulplattform && cd schulplattform`

## 6. Konfiguration (`.env`)

```bash
cp .env.example .env
nano .env
```

Diese Werte unbedingt setzen (Rest kann bleiben):

```ini
DJANGO_SECRET_KEY=<lange Zufallszeichenkette>
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=deine-domain.de
DJANGO_CSRF_TRUSTED_ORIGINS=https://deine-domain.de
DJANGO_SITE_URL=https://deine-domain.de

DJANGO_DB_NAME=schulplattform
DJANGO_DB_USER=schulplattform
DJANGO_DB_PASSWORD=<sicheres Passwort>

DOMAIN=deine-domain.de
LETSENCRYPT_EMAIL=du@example.de
```

Einen sicheren `DJANGO_SECRET_KEY` erzeugen:

```bash
docker run --rm python:3.11-slim python -c "import secrets; print(secrets.token_urlsafe(50))"
```

`nano` speichern: `Strg+O`, `Enter`, dann `Strg+X`.

> E-Mail (für Einladungs- und Passwort-Links): ohne SMTP-Angaben werden Mails
> nur ins Server-Log geschrieben – die Einladungslinks stehen aber auch im
> Admin. Für echten Versand die `DJANGO_EMAIL_*`-Werte setzen.

## 7. Starten

```bash
docker compose up -d --build
```

Beim ersten Start werden Images gebaut, die Datenbank migriert und statische
Dateien gesammelt. Caddy holt automatisch ein HTTPS-Zertifikat für deine Domain.

Öffne `https://deine-domain.de` – die Startseite sollte erscheinen. 🎉

## 8. Erstes Admin-Konto & Einrichtung

```bash
docker compose exec web python manage.py createsuperuser
```

Dann im Browser `https://deine-domain.de/admin/` anmelden und:

1. Unter **Schulen** eine Schule anlegen.
2. Unter **Einladungen** eine Lehrkraft einladen (Link weitergeben) – oder eine
   eingegangene **Zugangsanfrage** genehmigen.
3. Als Lehrkraft einloggen, Klasse + Schüler/innen anlegen, QR-Dokument drucken.

## 9. Wartung automatisieren (Cron)

```bash
crontab -e
```

Am Ende einfügen (Pfad ggf. anpassen):

```cron
# Tägliches Backup um 2:30 Uhr
30 2 * * * cd /root/schulplattform && ./scripts/backup.sh >> /var/log/schulplattform-backup.log 2>&1
# Monatliches Löschen alter Abgaben
0 3 1 * * cd /root/schulplattform && docker compose exec -T web python manage.py purge_submissions >> /var/log/schulplattform-purge.log 2>&1
```

> Kopiere die Backups regelmäßig auf einen zweiten Ort (anderer Server /
> verschlüsselter EU-Cloudspeicher).

## 10. Updates einspielen

Neuen Code aufspielen (Variante A oder B aus Schritt 5), dann:

```bash
cd /root/schulplattform
docker compose up -d --build
```

Migrationen und das Sammeln statischer Dateien laufen automatisch.

## Troubleshooting

- **Seite nicht erreichbar / kein Zertifikat:** DNS-A-Record korrekt auf die
  Server-IP? Ports 80/443 in der Firewall offen? Logs ansehen:
  `docker compose logs caddy` und `docker compose logs web`.
- **„Bad Request (400)":** `DJANGO_ALLOWED_HOSTS` enthält deine Domain?
- **Formular-Fehler beim Absenden:** `DJANGO_CSRF_TRUSTED_ORIGINS=https://deine-domain.de` gesetzt?
- **Status der Container:** `docker compose ps`.
- **Neu starten:** `docker compose restart`.

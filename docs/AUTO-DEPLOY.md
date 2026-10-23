# Auto-Deploy einrichten

Ziel: Sobald Code nach `main` gelangt (z. B. ein gemergter Pull Request), wird
der Server **von allein** aktualisiert. Du musst dich dann nie wieder per SSH
einloggen und `update.sh` tippen. Du kannst den Deploy außerdem jederzeit per
Knopfdruck in GitHub auslösen.

Der Workflow dafür liegt schon im Repo: `.github/workflows/deploy.yml`.
Er loggt sich nach einem Push auf `main` per SSH auf dem Server ein, holt den
neuen Stand und baut die Container neu.

> **Voraussetzung:** Auf dem Server kannst du `bash scripts/update.sh` schon von
> Hand ausführen (d. h. `git` kann den Code holen). Falls `git` dort nach einem
> Passwort/Token fragt, muss der Server-Zugang zum Repo einmal eingerichtet
> sein – melde dich dann, das klären wir separat.

---

## Schritt 1: Deploy-Schlüssel erzeugen (auf deinem Mac)

Ein eigenes SSH-Schlüsselpaar nur für den Deploy (nicht dein persönliches):

```bash
ssh-keygen -t ed25519 -C "github-deploy" -f ~/.ssh/hebid_deploy -N ""
```

Das erzeugt zwei Dateien:
- `~/.ssh/hebid_deploy`      → **privater** Schlüssel (geheim, kommt als Secret zu GitHub)
- `~/.ssh/hebid_deploy.pub`  → **öffentlicher** Schlüssel (kommt auf den Server)

## Schritt 2: Öffentlichen Schlüssel auf dem Server erlauben

Den öffentlichen Schlüssel beim Server als erlaubt eintragen (Benutzer/IP
anpassen – derselbe Zugang, mit dem du dich sonst einloggst):

```bash
ssh-copy-id -i ~/.ssh/hebid_deploy.pub root@46.224.216.58
```

Test, ob der Login mit dem neuen Schlüssel ohne Passwort klappt:

```bash
ssh -i ~/.ssh/hebid_deploy root@46.224.216.58 "echo ok"
```

## Schritt 3: Vier Secrets in GitHub hinterlegen

Im Repo auf GitHub: **Settings → Secrets and variables → Actions → New
repository secret**. Diese vier anlegen:

| Name | Wert |
|---|---|
| `DEPLOY_HOST` | `46.224.216.58` (die Server-IP) |
| `DEPLOY_USER` | der SSH-Benutzer, z. B. `root` |
| `DEPLOY_PATH` | der Projektordner auf dem Server, z. B. `/root/Schulplattform` |
| `DEPLOY_SSH_KEY` | der **komplette Inhalt** der Datei `~/.ssh/hebid_deploy` (privater Schlüssel) |

> Den privaten Schlüssel so auslesen und vollständig (inkl. der
> `-----BEGIN/END-----`-Zeilen) in das Secret einfügen:
> ```bash
> cat ~/.ssh/hebid_deploy
> ```
> Den Projektpfad findest du auf dem Server mit:
> ```bash
> cd ~/Schulplattform && pwd
> ```

## Schritt 4: Testen

- In GitHub auf **Actions → „Deploy auf den Server" → Run workflow** klicken.
- Der Lauf sollte grün werden. Danach ist jeder künftige Merge nach `main`
  automatisch live.

---

## Was der Deploy genau tut

Auf dem Server (im Projektordner):

```bash
git fetch --all --prune
git checkout main
git reset --hard origin/main      # exakt auf den main-Stand
docker compose up -d --build       # neu bauen & starten
```

Migrationen und das Sammeln statischer Dateien laufen beim Container-Start
automatisch (über `docker-entrypoint.sh`). Deine `.env` auf dem Server wird
nicht angefasst (sie ist nicht im Repo).

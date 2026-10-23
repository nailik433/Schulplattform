# Nächste Schritte – Arbeitsplan für den PC

Diese Liste arbeitest du der Reihe nach ab, wenn du wieder am Rechner sitzt.
Oben die Pflicht-Sachen (damit alles stabil läuft), danach die Komfort- und
Wunsch-Themen. Ganz unten steht ein **fertiges Briefing zum Einfügen in einen
Cowork-Chat**.

---

## Zuerst kurz verstanden: Wie läuft das mit den Lernumgebungen eigentlich?

Deine Frage war: *„Plane ich dann in Claude Code meinen Unterricht und er baut
mir automatisch die Lernumgebung?"* – Hier die ehrliche, einfache Antwort:

- **Das „Denken" bleibt wie bei Fobizz.** Du beschreibst die Stunde (dein
  Briefing), Claude plant mit dir und **baut die interaktive Lernumgebung als
  HTML** – genau wie damals das Bit-Labor. Das ist der Teil, den du schon
  kennst und magst.
- **Neu ist nur das Ablegen.** Früher hast du die fertige Animation als
  separates Artifact bekommen und irgendwo gespeichert. Jetzt legt Claude sie
  **direkt in die richtige Klasse deiner Plattform** – du musst nichts mehr
  kopieren. Die Animation liegt dort, wo die Schüler sie finden.
- **„Automatisch" heißt also:** nicht „Claude kennt deinen Lehrplan von allein",
  sondern „Claude speichert das fertige Ergebnis selbst in der Plattform,
  statt dass du es per Hand überträgst".

**Wichtig fürs Verständnis – Cowork vs. Code:**

| | Cowork | Claude Code |
|---|---|---|
| Wofür | Dein Alltag: Planung, Arbeitsblätter, Folien, Stoffverteilung, Lernumgebungen bauen | Nur wenn am *Quellcode der Plattform* etwas geändert wird |
| Ablegen in der Plattform | über den **eingebauten Connector** (Punkt 4) oder das Briefing/die API | über den **lokalen MCP-Connector** oder ebenfalls den eingebauten |
| Empfehlung für dich | **Hier bleibst du.** | Nur bei Bedarf |

➡️ **Kurz: Du musst NICHT nach Claude Code umziehen.** Plane weiter in Cowork –
mit dem eingebauten Connector (Punkt 4) hat Claude dort alle Werkzeuge.

---

## 1. ✅ Pflicht: Code auf `main` zusammenführen

**Warum:** Aktuell liegt die ganze Arbeit auf dem Zweig
`claude/school-platform-worksheets-c0x6aj`. Der `main`-Zweig ist praktisch
leer. Solange das so ist, ist alles fragil: Server-Updates und Auto-Deploy
brauchen einen stabilen Hauptzweig.

**Was zu tun ist (eine der beiden Varianten):**
- [ ] **Variante A (empfohlen, einfach):** Schreib mir in einem Claude-Code-Chat
      „Bitte öffne einen Pull Request von dem Arbeitszweig nach `main` und
      merge ihn." → Ich erstelle den PR, du klickst auf GitHub auf „Merge".
- [ ] **Variante B (selbst):** Auf GitHub einen Pull Request von
      `claude/school-platform-worksheets-c0x6aj` → `main` erstellen und mergen.

> Danach ist `main` der echte Stand, und wir können den Server sauber darauf
> ausrichten.

---

## 2. ✅ Pflicht: Server auf den neuesten Stand bringen

Auf dem Server liegen die neuen Funktionen (KI-Schnittstelle, ZIP-Download,
Import, Apple-Design …) vermutlich noch nicht. Erst nach dem Update sind sie
unter `hebid.de` live.

- [ ] Per SSH auf den Hetzner-Server einloggen (IP `46.224.216.58`).
- [ ] Prüfen, auf welchem Zweig der Server steht:
      ```bash
      cd ~/Schulplattform && git branch --show-current
      ```
- [ ] Falls nicht `main` (und du hast Punkt 1 gemacht): auf `main` wechseln:
      ```bash
      git checkout main
      ```
- [ ] Update einspielen:
      ```bash
      bash scripts/update.sh
      ```
- [ ] Im Browser `https://hebid.de` öffnen und prüfen: Login klappt, im
      Dashboard gibt es den Button **„KI & API"**, auf einer
      Arbeitsblatt-Seite den Button **„Alle Abgaben (ZIP)"**.
- [ ] Einmalig die Wartung automatisieren (tägliches Backup + Löschkonzept):
      ```bash
      bash scripts/install-cron.sh
      ```

---

## 3. ✅ Pflicht/Wunsch: Auto-Deploy einrichten (dein „Claude spielt Updates ein"-Wunsch)

**Was es bringt:** Nach dem Zusammenführen von Code wird der Server **von allein**
aktualisiert – du musst dich nie wieder per SSH einloggen und `update.sh`
tippen. Weder du noch ich brauchen dafür dauerhaften Serverzugriff.

**Wie:** Ein GitHub-Actions-Workflow loggt sich nach einem Merge nach `main`
automatisch per Deploy-Schlüssel auf dem Server ein und führt das Update aus.

**Status:** Der Workflow ist schon gebaut (`.github/workflows/deploy.yml`),
die Anleitung steht in [`docs/AUTO-DEPLOY.md`](./AUTO-DEPLOY.md).

- [ ] Deploy-Schlüssel auf dem Mac erzeugen und auf dem Server erlauben
      (Schritte 1–2 in AUTO-DEPLOY.md).
- [ ] **4 GitHub-Secrets** hinterlegen: `DEPLOY_HOST`, `DEPLOY_USER`,
      `DEPLOY_PATH`, `DEPLOY_SSH_KEY` (Schritt 3).
- [ ] In GitHub unter **Actions → „Deploy auf den Server" → Run workflow**
      testen. Danach aktualisiert sich der Server nach jedem Merge nach `main`
      von allein.

---

## 4. ☕ Cowork-Connector hinzufügen (2 Minuten, keine Installation)

**Geklärt und gebaut:** Cowork kann nur *Remote*-Connector – deshalb steckt der
MCP-Server jetzt **direkt in der Plattform**. Du fügst ihn einmal in Claude
hinzu, danach hat Claude in Cowork fertige Werkzeuge („Klassen auflisten“,
„Lernumgebung anlegen“, „… aktualisieren“) und schreibt direkt in die Klasse.

- [ ] In der Plattform: Dashboard → **„KI & API“** → **Connector-URL kopieren**
      (`https://hebid.de/mcp/<schlüssel>/` – wie ein Passwort behandeln).
- [ ] In Claude: **Customize → Connectors → Add custom connector** → Name
      „Schulplattform“, URL einfügen → Hinzufügen.
- [ ] In Cowork testen: „Zeig mir meine Klassen.“

> Für **Claude Code / Claude Desktop** gibt es zusätzlich den lokalen Connector
> (Anleitung in [`mcp/README.md`](../mcp/README.md), Variante B) – optional.

---

## 5. 📋 Dein normaler Arbeitsablauf in Cowork (so nutzt du es im Alltag)

So baust du ab jetzt eine Stunde mit Lernumgebung – **ohne Chrome, ohne
Copy-Paste**:

- [ ] In Cowork das Briefing aus [`docs/COWORK-BRIEFING.md`](./COWORK-BRIEFING.md)
      einmal in die **Projekt-Anweisungen** deines Cowork-Projekts einfügen und
      den API-Schlüssel eintragen (den Platzhalter ersetzen).
- [ ] Dann im Chat ganz normal planen: „Plane mir Informatik 7, Stunde zu …,
      die Schüler sollen sich das selbst erarbeiten. Bau dazu eine Lernumgebung
      und leg sie in Klasse R7a ab."
- [ ] Claude baut die HTML-Lernumgebung und speichert sie in der Klasse; du
      bekommst eine Vorschau-URL zum Testen.

---

## 6. 🎯 Feature-Wünsche für die Plattform (wenn du Lust hast)

Das sind Dinge für künftige **Claude-Code**-Sessions (jeweils eigener, kleiner
Chat – einfach den Punkt hineinkopieren):

- [ ] **Lernfortschritts-Übersicht pro Klasse** – eine Seite, die über alle
      Lernumgebungen und Abgaben zeigt, wer wie weit ist (offen/erledigt,
      Punkte). *(Der größte noch offene Punkt.)*
- [ ] **Bequemer Foto-/Kamera-Upload am Handy** für Schüler-Abgaben (direkt aus
      der Kamera statt Datei suchen).
- [ ] **Schüler-Dashboard „offen / erledigt"** mit hervorgehobenen Fristen.
- [ ] **Abgabe nach Frist sperren** (optional, statt nur „verspätet" zu
      markieren).

---

## 7. 📎 Fertiges Briefing zum Einfügen in einen neuen Cowork-Chat

> Kopiere den folgenden Block in einen neuen Cowork-Chat (oder in die
> Projekt-Anweisungen), wenn du direkt loslegen willst. Trag einmal deinen
> API-Schlüssel ein.

```text
Du hilfst mir bei der Unterrichtsplanung und baust interaktive Lernumgebungen,
die du direkt in meine Schulplattform legst.

MEINE PLATTFORM
- Basis-URL: https://hebid.de
- API-Schlüssel: [HIER MEINEN SCHLÜSSEL AUS „KI-Prompt & API" EINTRAGEN]
- Authentifizierung: Header „X-API-Key: <schlüssel>"

WAS DU KANNST
- Klassen mit IDs abrufen:  GET  https://hebid.de/api/classes
- Lernumgebung anlegen:     POST https://hebid.de/api/lessons
  Body: {"class_id": <id>, "title": "<titel>", "html": "<vollständiges HTML>"}
- Aktualisieren: dieselbe POST-Anfrage mit zusätzlichem Feld "id": <lesson-id>
  (Tipp: HTML in eine Datei schreiben und die JSON mit einem kleinen Skript
   bauen, damit Anführungszeichen/Zeilenumbrüche sauber escaped werden.)

SO ARBEITE ICH
1. Wir planen eine Stunde bildungsplan-bezogen; ich will wenig erklären, die
   Schüler erarbeiten sich den Stoff selbst.
2. Papier-Material (Sicherung, Verlaufsplan, Musterlösung) erstellst du wie
   gewohnt als Dateien.
3. Die interaktive Lernumgebung baust du als HTML und legst sie über die API
   DIREKT in der passenden Klasse an (nicht als separates Artifact).
4. Du gibst mir die teacher_url zum Testen zurück.

ANFORDERUNGEN AN DAS HTML
- Eine vollständige, in sich geschlossene Datei (beginnt mit <!DOCTYPE html>,
  CSS/JS inline, externe Dinge nur per CDN).
- Mobil & iPad zuerst: responsive, große Tap-Ziele, ruhiges klares Design.
- Interaktiv & selbsterklärend: Erklärung + Animation + Aufgaben mit direktem
  Feedback (gern mehrere Stationen, wie beim Bit-Labor). Rechnerisch prüfen,
  dass alles stimmt.
- Keine personenbezogenen Daten abfragen (keine Namen) – die Plattform ordnet
  Ergebnisse automatisch der/dem eingeloggten Schüler/in zu.
- Wenn es Punkte gibt, am Ende melden:
  window.parent.postMessage({type:'lesson_result', score: PUNKTE, max: MAX,
  completed:true}, '*');

Lege eine Lernumgebung erst an, wenn ich es sage. Zeig mir vorher kurz das
Konzept (Stationen/Aufgaben), dann baust du das HTML und legst es ab.
```

---

_Reihenfolge-Empfehlung: **1 → 2 → 3** zuerst (Fundament & Server), dann nach
Lust **5** (loslegen in Cowork) und bei Bedarf **4** (MCP) bzw. **6** (Features)._

# Cowork-Briefing: Lernumgebungen direkt in die Schulplattform bauen

Diese Datei ist als **Projekt-Anweisung für Cowork / Claude Code** gedacht.
Kopiere den Inhalt in die Anweisungen deines Cowork-Projekts (oder füge ihn zu
Beginn eines Chats ein). Damit kann Claude interaktive Lernumgebungen **direkt
in deine Schulplattform** schreiben – ohne Chrome, ohne Copy-Paste. Die
Animationen liegen dann bei der Klasse auf der Plattform, nicht als separates
Artifact.

---

## Kontext für Claude

Ich (die Lehrkraft) betreibe eine eigene Schulplattform unter
**`https://hebid.de`**. Schüler/innen melden sich dort nur mit einem Token an
(kein Name, kein Passwort). In einer Klasse kann ich „Lernumgebungen" ablegen –
das sind **vollständige, interaktive HTML-Seiten** (mit Animationen,
Simulationen, Aufgaben). Schüler/innen öffnen sie und bekommen sofort Feedback.

Du (Claude) kannst solche Lernumgebungen **über eine HTTP-API** anlegen. Nutze
dafür das Terminal (curl) oder HTTP-Requests.

> **Noch bequemer in Cowork:** Die Plattform hat einen eingebauten
> Connector. Einmal unter **Customize → Connectors → Add custom** die
> Connector-URL von der Seite „KI & API“ eintragen – dann hast du die
> Werkzeuge `klassen_auflisten`, `lernumgebungen_auflisten`,
> `lernumgebung_anlegen` und `lernumgebung_aktualisieren` direkt im Chat und
> brauchst kein curl. Die HTML-Anforderungen unten gelten weiterhin.

### Zugang (einmal eintragen)
- Basis-URL: `https://hebid.de`
- API-Schlüssel (geheim halten): `[HIER MEINEN API-SCHLÜSSEL EINTRAGEN]`
  (finde ich in der Plattform unter „KI-Prompt & API")
- Authentifizierung: Header `X-API-Key: <schlüssel>` bei jeder Anfrage.

### Werkzeuge (Endpunkte)

**1. Klassen mit IDs abrufen** (brauchst du, um die richtige `class_id` zu finden):
```bash
curl -s -H "X-API-Key: $KEY" https://hebid.de/api/classes
```
Antwort: `{"classes":[{"id":1,"name":"R7a","subject":"Informatik","school":"HHRS","students":28}, ...]}`

**2. Lernumgebung anlegen:**
```bash
curl -s -X POST https://hebid.de/api/lessons \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d @payload.json
# payload.json: {"class_id": 1, "title": "Bit-Labor", "html": "<!DOCTYPE html>..."}
```
Tipp: Schreibe das HTML in eine Datei und baue die JSON mit einem kleinen
Skript (z. B. Python `json.dump`), damit Anführungszeichen/Zeilenumbrüche im
HTML sauber escaped werden. Niemals das HTML von Hand in die Kommandozeile
quetschen.

**3. Bestehende Lernumgebung aktualisieren:** dieselbe POST-Anfrage mit
zusätzlichem Feld `"id": <lesson-id>` (die ID kommt aus der Antwort beim
Anlegen).

Antwort beim Anlegen: `{"id": 12, "title": "...", "teacher_url": "https://hebid.de/lernumgebung/12/"}`

---

## Anforderungen an die HTML-Lernumgebung

- **Eine vollständige, in sich geschlossene Datei**: beginnt mit
  `<!DOCTYPE html>`, alles inline (CSS in `<style>`, JS in `<script>`). Keine
  lokalen Dateien. Externe Fonts/Skripte nur per CDN, sonst nichts Externes.
- **Mobil & iPad zuerst**: responsive, große Tap-Ziele, auf Smartphone-Breite
  getestet (so wie das bisherige „Bit-Labor"). Ruhiges, klares Design.
- **Interaktiv & selbsterklärend**: Erklärungen + Animationen (CSS/SVG/Canvas) +
  Aufgaben mit direktem Feedback (z. B. mehrere Stationen wie beim Bit-Labor:
  Schalter/Stellenwerte, Möglichkeiten zählen, Code-Maschine …). Rechnerisch
  prüfen, dass alles stimmt.
- **Keine personenbezogenen Daten** abfragen (keine Namen). Die Plattform ordnet
  Ergebnisse automatisch der/dem eingeloggten Schüler/in zu.
- **Schnittstelle zur Plattform ist Pflicht** (siehe nächster Abschnitt): Ergebnis,
  Einzelergebnisse, Zwischenstand und Fortschritt. Die Plattform kann nicht in die
  HTML-Datei schauen – sie weiß nur, was die Lernumgebung per `postMessage` meldet.
  Ohne diese Meldungen sehe ich als Lehrkraft nur „geöffnet“.

---

## Schnittstelle zur Plattform – Pflicht (Ergebnis, Fortschritt, Zwischenstand)

Die iPads wechseln zwischen den Schülern. Lernumgebungen dürfen deshalb **nichts in
`localStorage`/`sessionStorage`** ablegen – der nächste Schüler würde den Stand des
vorherigen sehen. Stattdessen liegt der Zwischenstand **auf dem Server, pro
Schülerkonto**. Das geht über drei kleine Nachrichten:

| Richtung | Nachricht | Bedeutung |
|---|---|---|
| Lernumgebung → Plattform | `{type:'lesson_state_request'}` | „Gib mir meinen gespeicherten Stand.“ |
| Plattform → Lernumgebung | `{type:'lesson_state', state: <JSON oder null>}` | `null` heißt: noch nichts gespeichert, neu beginnen. |
| Lernumgebung → Plattform | `{type:'lesson_state_save', state: <JSON>, progress: 0-100}` | Stand speichern (entprellt ca. 1,5 s, letzte Nachricht gewinnt, max. 64 KB, `null` löscht). `progress` zeigt mir einen Fortschrittsbalken. |
| Lernumgebung → Plattform | `{type:'lesson_result', score, max, completed, extra, extra_max, detail}` | Ergebnis. `detail` = flaches Objekt mit Einzelergebnissen, z. B. `{"Aufgabe 1":"richtig"}` – sichtbar in der Detailansicht. |
| Plattform → Lernumgebung | `{type:'lesson_state_saved', ok:true}` | Optionale Rückmeldung. |

- Antwort nur annehmen, wenn `event.source === window.parent`.
- Kommt nach ca. 1,5 s keine Antwort (z. B. Vorschau in neuem Tab), mit leerem Stand starten.
- In der **Lehrer-Vorschau** wird nichts gespeichert (Antwort immer `state:null`).
- Zusatzpunkte beim Ergebnis: `lesson_result` darf zusätzlich `extra` und `extra_max` enthalten.
- Nach dem Anlegen prüft die Plattform das HTML und liefert fehlende Teile als **Hinweise** zurück (`hinweise` in der API-Antwort, im Connector als „⚠ HINWEISE“). Jeden Hinweis beheben und mit `lernumgebung_aktualisieren` erneut senden.
- Ein fertiges, getestetes Beispiel steht in [`docs/beispiel-zwischenstand.html`](./beispiel-zwischenstand.html);
  der Helfer `PlatformState` daraus lässt sich direkt übernehmen.
- Lehrkräfte sehen pro Schüler/in Fortschrittsbalken und Einzelergebnisse und können den Stand zurücksetzen.

---

## Standard-Ablauf (so arbeite ich)

1. Wir planen eine Stunde (Bildungsplan-bezogen), ich will wenig erklären – die
   Schüler erarbeiten sich den Stoff selbst.
2. Papier-Material (Sicherung, Verlaufsplan, Musterlösung) erstellst du wie
   bisher als Dateien (die lege ich in OneDrive ab bzw. lade sie als
   „Arbeitsblatt" in der Plattform hoch).
3. Die **interaktive Lernumgebung** baust du als HTML und legst sie über die
   API **direkt in der passenden Klasse** an (statt als separates Artifact).
4. Du gibst mir die `teacher_url` zurück, damit ich sie in der Plattform
   ansehen/testen kann. Schüler/innen finden sie nach dem Login automatisch.

> Hinweis: Lege eine Lernumgebung erst an, wenn ich es sage. Zeig mir vorher
> kurz das Konzept (Stationen/Aufgaben), dann baust du die HTML und postest sie.

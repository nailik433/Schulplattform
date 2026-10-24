# TODO / Nächste Schritte

Notizen für die nächsten Sessions. (Status-Hinweise von Claude in Klammern –
nur zur Orientierung, die Wünsche darüber sind maßgeblich.)

## Zuerst: Server live schalten (angefangen)
- Server bei Hetzner läuft (IP `46.224.216.58`), Code ist aufgespielt.
- Domain **hebid.de** ist bei IONOS registriert; wartet darauf, im IONOS
  Domain-Center sichtbar zu werden.
- **Offen:** bei IONOS den **A-Eintrag** `@ → 46.224.216.58` setzen, dann auf
  dem Server `bash scripts/server-setup.sh` ausführen (fragt Domain + E-Mail),
  Admin anlegen. Danach ist `https://hebid.de` live.

## Feature-Wünsche

### 1. Schnittstelle zur Erstellung digitaler Lernumgebungen per KI
✅ **Umgesetzt.** App `lessons`: interaktive Lernumgebungen als vollständige,
sandboxed-angezeigte HTML-Seiten (mit Animationen); Erstellung per Einfügen
oder per **API mit Schlüssel** (KI-Schnittstelle). Ergebnis-Rückmeldung der
HTML an die Plattform via postMessage; Lehrer-Ergebnisübersicht. Prompt + API
unter „KI-Prompt & API" im Dashboard.

### 2. Abgaben für Schüler
Schüler können etwas hochladen (z. B. ein Foto) **bis zu einem Datum X**.
- (Grundfunktion existiert bereits: Abgaben mit Datei-Upload + Frist, inkl.
  „verspätet"-Markierung. Zu ergänzen/prüfen: bequemer Foto-/Kamera-Upload am
  Handy; optional: Abgabe nach Frist sperren statt nur markieren.)

### 3. Schüler-Loginscreen + Dashboard
Ein Login-Screen für Schüler und ein „Dashboard" mit den **offenen
Arbeitsaufträgen**.
- (Login per Token + QR existiert; Startseite zeigt Arbeitsblätter/Abgaben.
  Zu ergänzen: klareres Dashboard „offen / erledigt", Fristen hervorheben.)

### 4. Lehrer-Login-Bereich + Dashboard
Lehrer-Dashboard mit **Abgaben**, **Lernfortschritt** und der Möglichkeit,
**alle Abgaben einer Klasse herunterzuladen**.
Wichtiger Anwendungsfall: z. B. in Informatik ein Word-Dokument formatieren
lassen → Schüler laden ihr Ergebnis hoch → Lehrer lädt **alle „Lösungen" auf
einmal** herunter (ein Ordner mit z. B. 25 Abgaben) → dieser Ordner wird in
einem Claude-Chat freigegeben → Claude schreibt **Bewertungen**, vergibt
**Punkte anhand der Aufgaben** und zeigt, inwieweit die Aufgaben erreicht wurden.
- (Lehrer-Login + Abgabe-Übersicht je Arbeitsblatt existieren.
  ✅ **ZIP-Download umgesetzt:** Button „Alle Abgaben (ZIP)" auf der
  Arbeitsblatt-Seite. Pro Schüler/in ein Ordner (z. B. `7b-001/`) – genau
  das ermöglicht den Claude-Bewertungs-Workflow mit allen Abgaben auf einmal.
  Noch offen: Lernfortschritts-Übersicht pro Klasse.)

---
_Reihenfolge-Vorschlag für morgen: erst Server live (DNS + Deploy), dann
Punkt 4 (ZIP-Download) als größter Nutzen, danach 1, 2, 3._

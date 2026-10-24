"""The postMessage protocol between a learning environment (HTML in a sandboxed
iframe) and the platform page around it, described once for everyone who
needs to explain it: the MCP server instructions, the "KI & API" page and the
Cowork briefing. Also :func:`check_protocol`, which tells whoever uploads a
lesson what its HTML forgot to report."""

import re

LESSON_PROTOCOL = """\
SCHNITTSTELLE ZUR PLATTFORM – PFLICHT BEI JEDER LERNUMGEBUNG
Die Lernumgebung läuft isoliert in einem iframe. Die Plattform kann NICHT in die HTML-Datei
schauen und weiß nur das, was die HTML per postMessage meldet. Baust du die Meldungen nicht ein,
sieht die Lehrkraft nur „geöffnet“ – kein Ergebnis, keinen Fortschritt, und die Schüler/innen
verlieren ihren Stand. Baue deshalb in JEDE Lernumgebung ein:

1) ERGEBNIS (am Ende, und bei Zwischenpunkten mit completed:false):
   window.parent.postMessage({type:'lesson_result', score, max, completed:true,
       extra, extra_max, detail}, '*');
   - extra/extra_max: optionale Zusatzpunkte.
   - detail: Einzelergebnisse für die Lehrkraft als flaches Objekt aus kurzen Texten oder
     Zahlen, z. B. {"Aufgabe 1": "richtig", "Aufgabe 2": "falsch (Antwort: 7)", "Zeit (s)": 312}.
     Die Lehrkraft sieht sie in der Detailansicht. Keine Namen oder persönlichen Daten.

2) ZWISCHENSTAND pro Schüler/in. Er liegt auf dem Server und folgt dem Schülerkonto, weil die
   iPads zwischen Schülern wechseln. localStorage/sessionStorage/IndexedDB NICHT verwenden.
   - Beim Start den Stand anfordern:
       window.parent.postMessage({type:'lesson_state_request'}, '*');
     Antwort: {type:'lesson_state', state: <JSON oder null>}. null = noch nichts gespeichert,
     also neu beginnen. Kommt nach ca. 1,5 s keine Antwort (z. B. Vorschau in neuem Tab),
     ebenfalls mit leerem Stand starten.
   - Bei jeder relevanten Änderung speichern UND den Fortschritt in Prozent mitgeben:
       window.parent.postMessage({type:'lesson_state_save', state: <JSON>, progress: 0-100}, '*');
     progress zeigt der Lehrkraft einen Fortschrittsbalken (z. B. erledigte Aufgaben / alle
     Aufgaben * 100). Die Plattform entprellt (ca. 1,5 s), die letzte Nachricht gewinnt, maximal
     64 KB. state:null löscht den Stand. Optionale Rückmeldung: {type:'lesson_state_saved', ok}.
     Bleibt sie aus (Lehrer-Vorschau), ist das kein Fehler.
   - Nur kleine, serialisierbare Daten speichern (Antworten, Position, Zähler), keine Bilder.
   - Nachrichten nur annehmen, wenn event.source === window.parent.

3) NACH DEM ANLEGEN prüft die Plattform das HTML und meldet fehlende Teile als „Hinweise“
   zurück. Behebe jeden Hinweis und sende die Lernumgebung mit lernumgebung_aktualisieren
   erneut, bis keine Hinweise mehr kommen.

Fertiger Helfer zum Einfügen (am Anfang des <script>):
   const PlatformState = {
     load(callback) {
       let done = false;
       const finish = s => { if (!done) { done = true; callback(s); } };
       addEventListener('message', e => {
         if (e.source === parent && e.data && e.data.type === 'lesson_state') finish(e.data.state);
       });
       parent.postMessage({type: 'lesson_state_request'}, '*');
       setTimeout(() => finish(null), 1500);
     },
     save(state, progress) { parent.postMessage({type: 'lesson_state_save', state, progress}, '*'); },
     result(r) { parent.postMessage(Object.assign({type: 'lesson_result'}, r), '*'); }
   };
"""

# (needle, message). A lesson passes a check when its HTML contains the needle (regex).
_CHECKS = [
    (r"lesson_result",
     "Die Lernumgebung meldet kein Ergebnis (lesson_result). Die Lehrkraft sieht dann nur "
     "„geöffnet“, keine Punkte."),
    (r"lesson_state_request",
     "Die Lernumgebung lädt keinen Zwischenstand (lesson_state_request). Schüler/innen verlieren "
     "beim Schließen ihren Fortschritt."),
    (r"lesson_state_save",
     "Die Lernumgebung speichert keinen Zwischenstand (lesson_state_save)."),
]


def check_protocol(html):
    """Return a list of German hints about what ``html`` forgot to report to the
    platform (empty list = all good). Hints only, nothing is rejected: a purely
    static page is legitimate, but the author should decide that knowingly."""
    html = html or ""
    hints = [message for pattern, message in _CHECKS if not re.search(pattern, html)]
    # "progress" must travel with the save message itself (a CSS class .progress does not count).
    if "lesson_state_save" in html and not re.search(r"lesson_state_save[^;]{0,200}\bprogress\b", html):
        hints.append(
            "Der Zwischenstand wird ohne Fortschritt gespeichert: Gib bei lesson_state_save "
            "progress (0-100) mit, damit die Lehrkraft einen Fortschrittsbalken sieht."
        )
    if "lesson_result" in html and not re.search(r"\bdetail\b", html):
        hints.append(
            "Das Ergebnis enthält keine Einzelergebnisse (detail). Empfohlen: detail als flaches "
            "Objekt, z. B. {\"Aufgabe 1\": \"richtig\"}, damit die Lehrkraft nachvollziehen kann, "
            "wo es hakt."
        )
    if re.search(r"\b(localStorage|sessionStorage|indexedDB)\b", html):
        hints.append(
            "Die Lernumgebung nutzt den Browser-Speicher (localStorage/sessionStorage/IndexedDB). "
            "Die iPads werden von mehreren Schülern geteilt, der nächste sähe den Stand des "
            "vorherigen. Nutze stattdessen lesson_state_save."
        )
    return hints

"""The postMessage protocol between a learning environment (HTML in a sandboxed
iframe) and the platform page around it, described once for everyone who
needs to explain it: the MCP server instructions, the "KI & API" page and the
Cowork briefing."""

LESSON_PROTOCOL = """\
SCHNITTSTELLE ZUR PLATTFORM (postMessage zwischen Lernumgebung und umgebender Seite)

1) Ergebnis (am Ende, wie bisher):
   window.parent.postMessage({type:'lesson_result', score, max, completed:true}, '*');
   Optional Zusatzpunkte: zusätzlich extra und extra_max mitsenden.

2) Zwischenstand pro Schüler/in. Er liegt auf dem Server und folgt dem Schülerkonto,
   weil die iPads zwischen Schülern wechseln. localStorage/sessionStorage NICHT verwenden.
   - Beim Start den Stand anfordern:
       window.parent.postMessage({type:'lesson_state_request'}, '*');
     Antwort: {type:'lesson_state', state: <JSON oder null>}. null = noch nichts gespeichert,
     also neu beginnen. Kommt nach ca. 1,5 s keine Antwort (z. B. Vorschau in neuem Tab),
     ebenfalls mit leerem Stand starten.
   - Bei jeder relevanten Änderung speichern:
       window.parent.postMessage({type:'lesson_state_save', state: <JSON>}, '*');
     Die Plattform entprellt (ca. 1,5 s), die letzte Nachricht gewinnt, maximal 64 KB.
     state:null löscht den Stand. Optionale Rückmeldung: {type:'lesson_state_saved', ok:true|false}.
   - Nur kleine, serialisierbare Daten speichern (Antworten, Position, Zähler), keine Bilder.
   - Nachrichten nur annehmen, wenn event.source === window.parent.
   - In der Lehrer-Vorschau wird nichts gespeichert (Antwort immer state:null).

Fertiger Helfer zum Einfügen:
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
     save(state) { parent.postMessage({type: 'lesson_state_save', state}, '*'); }
   };
"""

# MCP-Connector für die Schulplattform

Damit bekommt **Claude Code / Claude Desktop** fertige Werkzeuge, um
interaktive Lernumgebungen **direkt in deine Plattform** (`hebid.de`) zu
schreiben – ohne curl, ohne Chrome. Statt Kommandozeilen-Befehle hat Claude
dann diese Aktionen:

> **Wichtig – nicht für Cowork:** Dies ist ein **lokaler** MCP-Server. Laut
> Anthropic-Support laufen lokale MCP-Server nur in **Claude Code** und
> **Claude Desktop**, nicht in **Cowork**. In Cowork nutzt du stattdessen das
> [`docs/COWORK-BRIEFING.md`](../docs/COWORK-BRIEFING.md) (API) – oder künftig
> einen Remote-MCP-Endpunkt in der Plattform selbst.

- **`klassen_auflisten`** – zeigt deine Klassen mit ihren IDs
- **`lernumgebung_anlegen`** – legt eine neue Lernumgebung in einer Klasse an
- **`lernumgebung_aktualisieren`** – ändert eine bestehende
- **`lernumgebung_aus_datei`** – legt eine an und liest das HTML aus einer Datei

Einmal einrichten, danach nie wieder dran denken.

---

## 1. Voraussetzung

Python 3.10+ und das Paket `mcp`:

```bash
python3 -m pip install mcp
```

> Falls du `uv` nutzt, kannst du Schritt 1 überspringen – unten gibt es eine
> Variante, die die Abhängigkeit automatisch lädt.

## 2. API-Schlüssel holen

In der Plattform einloggen → **„KI-Prompt & API"** → Schlüssel kopieren
(beginnt mit `sk_…`).

## 3. Connector in Claude Code registrieren

Einmaliger Befehl (Pfad zur Datei anpassen):

```bash
claude mcp add schulplattform \
  -e SCHULPLATTFORM_URL=https://hebid.de \
  -e SCHULPLATTFORM_API_KEY=sk_DEIN_SCHLUESSEL \
  -- python3 /voller/pfad/zu/Schulplattform/mcp/schulplattform_mcp.py
```

**Variante mit `uv`** (lädt `mcp` automatisch, keine Installation nötig):

```bash
claude mcp add schulplattform \
  -e SCHULPLATTFORM_URL=https://hebid.de \
  -e SCHULPLATTFORM_API_KEY=sk_DEIN_SCHLUESSEL \
  -- uv run --with mcp python /voller/pfad/zu/Schulplattform/mcp/schulplattform_mcp.py
```

Prüfen, ob er läuft:

```bash
claude mcp list
```

## 4. Nutzen

Im Chat einfach sagen, z. B.:

> „Zeig mir meine Klassen." → Claude ruft `klassen_auflisten` auf.
>
> „Bau für R7a (ID 3) eine Lernumgebung ‚Bit-Labor' zum Thema Bit/Byte und
> leg sie in der Klasse an." → Claude baut das HTML und ruft
> `lernumgebung_anlegen` auf; du bekommst die Lehrer-URL zum Testen zurück.

Die Animationen liegen dann bei der Klasse auf der Plattform – nicht mehr als
separates Artifact.

---

## Projektweite Konfiguration (optional)

Wenn du Cowork-Sitzungen **in diesem Repository** startest, kannst du statt des
`claude mcp add`-Befehls die Datei `.mcp.json` im Projektwurzelverzeichnis
nutzen (Vorlage: [`mcp/mcp.json.example`](./mcp.json.example)). Den
API-Schlüssel dabei **nicht** in die Datei schreiben, sondern als
Umgebungsvariable `SCHULPLATTFORM_API_KEY` setzen – die Vorlage liest ihn von
dort (`${SCHULPLATTFORM_API_KEY}`).

## Hinweise zum HTML

Die Anforderungen an die Lernumgebungen (vollständige, in sich geschlossene,
iPad-taugliche HTML-Seite, keine personenbezogenen Daten, optionale
Ergebnis-Rückmeldung per `postMessage`) stehen in
[`docs/COWORK-BRIEFING.md`](../docs/COWORK-BRIEFING.md). Dieses Briefing und der
MCP-Connector ergänzen sich: das Briefing beschreibt *was* gebaut wird, der
Connector ist das bequeme *Wie* beim Ablegen.

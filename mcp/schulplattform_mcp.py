#!/usr/bin/env python3
"""MCP-Server für die Schulplattform (hebid.de).

Gibt einem KI-Assistenten (Claude in Cowork / Claude Code) saubere Werkzeuge,
um interaktive Lernumgebungen direkt in der Plattform anzulegen – ohne curl,
ohne Chrome. Spricht die HTTP-API der Plattform an:

    GET  /api/classes   -> Klassen auflisten
    POST /api/lessons   -> Lernumgebung anlegen / aktualisieren

Konfiguration über Umgebungsvariablen:
    SCHULPLATTFORM_URL       Basis-URL (Standard: https://hebid.de)
    SCHULPLATTFORM_API_KEY   API-Schlüssel (aus „KI-Prompt & API" im Dashboard)

Start (für Claude Code):  siehe mcp/README.md
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

# FastMCP wurde in der mcp-SDK 2.x in MCPServer umbenannt. Beide bieten die
# gleichen Methoden (`.tool()` als Decorator, `.run()` mit stdio als Standard),
# daher funktioniert dieser Server mit mcp 1.x und 2.x.
try:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server
except ModuleNotFoundError:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as _Server

# --------------------------------------------------------------------------
# Konfiguration
# --------------------------------------------------------------------------

BASE_URL = os.environ.get("SCHULPLATTFORM_URL", "https://hebid.de").rstrip("/")
API_KEY = os.environ.get("SCHULPLATTFORM_API_KEY", "").strip()

mcp = _Server("schulplattform")


class PlattformFehler(Exception):
    """Fehler bei der Kommunikation mit der Plattform (für den Assistenten lesbar)."""


def _request(method: str, path: str, payload: dict | None = None) -> dict:
    """Eine authentifizierte Anfrage an die Plattform-API senden."""
    if not API_KEY:
        raise PlattformFehler(
            "Kein API-Schlüssel gesetzt. Bitte die Umgebungsvariable "
            "SCHULPLATTFORM_API_KEY mit dem Schlüssel aus „KI-Prompt & API\" belegen."
        )

    url = f"{BASE_URL}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-API-Key", API_KEY)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        try:
            detail = json.loads(detail).get("error", detail)
        except ValueError:
            pass
        if exc.code == 401:
            raise PlattformFehler(
                "API-Schlüssel ungültig oder abgelaufen. Bitte unter "
                "„KI-Prompt & API\" einen neuen erstellen und SCHULPLATTFORM_API_KEY "
                "aktualisieren."
            ) from exc
        raise PlattformFehler(f"Plattform-Fehler ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise PlattformFehler(
            f"Plattform unter {BASE_URL} nicht erreichbar: {exc.reason}"
        ) from exc

    try:
        return json.loads(body) if body else {}
    except ValueError as exc:
        raise PlattformFehler("Antwort der Plattform war kein gültiges JSON.") from exc


# --------------------------------------------------------------------------
# Werkzeuge
# --------------------------------------------------------------------------

@mcp.tool()
def klassen_auflisten() -> str:
    """Listet alle Klassen der Lehrkraft mit ihren IDs auf.

    Nutze dieses Werkzeug, um die richtige `klasse_id` zu finden, bevor du eine
    Lernumgebung anlegst. Gibt je Klasse ID, Name, Fach, Schule und
    Schülerzahl zurück.
    """
    data = _request("GET", "/api/classes")
    classes = data.get("classes", [])
    if not classes:
        return "Keine Klassen gefunden. Lege zuerst im Dashboard eine Klasse an."
    zeilen = [
        f"- ID {c['id']}: {c['name']}"
        + (f" ({c['subject']})" if c.get("subject") else "")
        + f" · {c.get('school', '')} · {c.get('students', 0)} Schüler/innen"
        for c in classes
    ]
    return "Klassen:\n" + "\n".join(zeilen)


@mcp.tool()
def lernumgebungen_auflisten(klasse_id: int) -> str:
    """Listet die vorhandenen Lernumgebungen einer Klasse (ID, Titel, zuletzt
    geändert, Lehrer-URL) – z. B. um eine davon zu aktualisieren.

    Args:
        klasse_id: ID der Klasse (aus `klassen_auflisten`).
    """
    data = _request("GET", f"/api/lessons?class_id={int(klasse_id)}")
    lessons = data.get("lessons", [])
    if not lessons:
        return "In dieser Klasse gibt es noch keine Lernumgebungen."
    zeilen = [
        f"- ID {l['id']}: {l['title']} · geändert {l.get('updated_at', '')} · {l.get('teacher_url', '')}"
        for l in lessons
    ]
    return "Lernumgebungen:\n" + "\n".join(zeilen)


@mcp.tool()
def lernumgebung_anlegen(klasse_id: int, titel: str, html: str) -> str:
    """Legt eine neue interaktive Lernumgebung in einer Klasse an.

    Args:
        klasse_id: ID der Zielklasse (aus `klassen_auflisten`).
        titel: Titel der Lernumgebung (z. B. „Bit-Labor").
        html: Vollständige, in sich geschlossene HTML-Seite (beginnt mit
            <!DOCTYPE html>, CSS/JS inline, mobil/iPad-tauglich). Keine
            personenbezogenen Daten abfragen. Punkte optional am Ende per
            `window.parent.postMessage({type:'lesson_result', score, max,
            completed:true}, '*')` melden.

    Gibt die ID und die Lehrer-URL zum Ansehen/Testen zurück.
    """
    data = _request(
        "POST", "/api/lessons",
        {"class_id": klasse_id, "title": titel, "html": html},
    )
    return (
        f"Lernumgebung angelegt (ID {data.get('id')}).\n"
        f"Zum Ansehen/Testen: {data.get('teacher_url')}\n"
        f"Schüler/innen finden sie nach dem Login automatisch."
    )


@mcp.tool()
def lernumgebung_aktualisieren(lernumgebung_id: int, titel: str, html: str) -> str:
    """Aktualisiert eine bestehende Lernumgebung (Titel + HTML ersetzen).

    Args:
        lernumgebung_id: ID der zu ändernden Lernumgebung (aus dem Anlegen).
        titel: neuer Titel.
        html: vollständige, ersetzte HTML-Seite (siehe `lernumgebung_anlegen`).
    """
    data = _request(
        "POST", "/api/lessons",
        {"id": lernumgebung_id, "title": titel, "html": html},
    )
    return (
        f"Lernumgebung {data.get('id')} aktualisiert.\n"
        f"Zum Ansehen/Testen: {data.get('teacher_url')}"
    )


@mcp.tool()
def lernumgebung_aus_datei(klasse_id: int, titel: str, html_pfad: str) -> str:
    """Wie `lernumgebung_anlegen`, liest das HTML aber aus einer lokalen Datei.

    Praktisch für große Seiten: schreibe das HTML zuerst in eine Datei
    (z. B. bit-labor.html) und übergib hier nur den Dateipfad. Das vermeidet
    Escaping-Probleme mit großen HTML-Blöcken.

    Args:
        klasse_id: ID der Zielklasse (aus `klassen_auflisten`).
        titel: Titel der Lernumgebung.
        html_pfad: Pfad zur HTML-Datei auf diesem Rechner.
    """
    try:
        with open(html_pfad, "r", encoding="utf-8") as fh:
            html = fh.read()
    except OSError as exc:
        raise PlattformFehler(f"HTML-Datei nicht lesbar: {exc}") from exc
    return lernumgebung_anlegen(klasse_id=klasse_id, titel=titel, html=html)


if __name__ == "__main__":
    mcp.run()

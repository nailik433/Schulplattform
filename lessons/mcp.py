"""Remote MCP server built into the platform (Streamable HTTP transport).

Lets Claude in Cowork / claude.ai use the platform as a *custom connector*
without installing anything: the teacher adds
``https://<domain>/mcp/<api-key>/`` under "Customize → Connectors". Clients
that can send headers may instead call ``/mcp`` with
``Authorization: Bearer <api-key>``.

The server is stateless and speaks JSON-RPC 2.0 over POST. It implements the
subset of the Model Context Protocol a tools-only server needs:
``initialize``, ``ping``, ``tools/list`` and ``tools/call`` (plus empty
``resources/list`` / ``prompts/list`` for clients that probe them).
Notifications are acknowledged with 202. The optional GET event stream and
session termination are not supported, which the protocol allows (405).
"""

import json

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .api import ApiError, classes_data, lessons_data, teacher_for_key, upsert_lesson
from .protocol import LESSON_PROTOCOL

PROTOCOL_VERSIONS = {"2025-06-18", "2025-03-26", "2024-11-05"}
LATEST_PROTOCOL = "2025-06-18"

SERVER_INFO = {"name": "schulplattform", "title": "Schulplattform", "version": "1.0.0"}

INSTRUCTIONS = (
    "Werkzeuge der Schulplattform der Lehrkraft. Lege Lernumgebungen als "
    "vollständige, in sich geschlossene HTML-Seiten an (<!DOCTYPE html>, CSS/JS "
    "inline, iPad-tauglich, keine personenbezogenen Daten). Ermittle die klasse_id "
    "zuerst mit klassen_auflisten.\n\n" + LESSON_PROTOCOL
)

HTML_DESCRIPTION = (
    "Vollständige HTML-Seite (beginnt mit <!DOCTYPE html>; CSS in <style>, JS in "
    "<script>; responsiv für iPad/Smartphone; keine Namen abfragen). Ergebnis und "
    "Zwischenstand per postMessage melden/laden (lesson_result, lesson_state_request, "
    "lesson_state_save); die genaue Beschreibung steht in den Server-Anweisungen."
)

TOOLS = [
    {
        "name": "klassen_auflisten",
        "title": "Klassen auflisten",
        "description": "Listet alle Klassen der Lehrkraft mit IDs, Fach, Schule und "
        "Schülerzahl. Zuerst aufrufen, um die richtige klasse_id zu finden.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "lernumgebungen_auflisten",
        "title": "Lernumgebungen auflisten",
        "description": "Listet die vorhandenen Lernumgebungen einer Klasse (ID, Titel, "
        "zuletzt geändert, Lehrer-URL) – z. B. um eine zu aktualisieren.",
        "inputSchema": {
            "type": "object",
            "properties": {"klasse_id": {"type": "integer", "description": "ID der Klasse"}},
            "required": ["klasse_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "lernumgebung_anlegen",
        "title": "Lernumgebung anlegen",
        "description": "Legt eine neue interaktive Lernumgebung in einer Klasse an. "
        "Gibt ID und Lehrer-URL zum Testen zurück; Schüler/innen sehen sie nach dem Login.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "klasse_id": {"type": "integer", "description": "ID der Zielklasse"},
                "titel": {"type": "string", "description": "Titel, z. B. „Bit-Labor“"},
                "html": {"type": "string", "description": HTML_DESCRIPTION},
            },
            "required": ["klasse_id", "titel", "html"],
            "additionalProperties": False,
        },
    },
    {
        "name": "lernumgebung_aktualisieren",
        "title": "Lernumgebung aktualisieren",
        "description": "Ersetzt Titel und HTML einer bestehenden Lernumgebung (gleiche URL, "
        "Ergebnisse bleiben erhalten).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lernumgebung_id": {"type": "integer", "description": "ID der Lernumgebung"},
                "titel": {"type": "string", "description": "Neuer Titel"},
                "html": {"type": "string", "description": HTML_DESCRIPTION},
            },
            "required": ["lernumgebung_id", "titel", "html"],
            "additionalProperties": False,
        },
    },
]


class ToolError(Exception):
    pass


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

def _int_arg(args, name):
    value = args.get(name)
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ToolError(f"Parameter „{name}“ fehlt oder ist keine Zahl.")


def _call_tool(teacher, name, args, base):
    try:
        if name == "klassen_auflisten":
            classes = classes_data(teacher)
            if not classes:
                return "Keine Klassen gefunden. Lege zuerst im Dashboard eine Klasse an."
            lines = [
                f"- ID {c['id']}: {c['name']}"
                + (f" ({c['subject']})" if c["subject"] else "")
                + f" · {c['school']} · {c['students']} Schüler/innen"
                for c in classes
            ]
            return "Klassen:\n" + "\n".join(lines)

        if name == "lernumgebungen_auflisten":
            lessons = lessons_data(teacher, _int_arg(args, "klasse_id"), base)
            if not lessons:
                return "In dieser Klasse gibt es noch keine Lernumgebungen."
            lines = [
                f"- ID {l['id']}: {l['title']} · geändert {l['updated_at']} · {l['teacher_url']}"
                for l in lessons
            ]
            return "Lernumgebungen:\n" + "\n".join(lines)

        if name == "lernumgebung_anlegen":
            data, _ = upsert_lesson(
                teacher,
                title=args.get("titel"),
                html=args.get("html"),
                class_id=_int_arg(args, "klasse_id"),
                base=base,
            )
            return (
                f"Lernumgebung angelegt (ID {data['id']}) in Klasse {data['class_name']}.\n"
                f"Zum Ansehen/Testen: {data['teacher_url']}\n"
                "Schüler/innen finden sie nach dem Login unter „Meine Aufgaben“."
            )

        if name == "lernumgebung_aktualisieren":
            data, _ = upsert_lesson(
                teacher,
                title=args.get("titel"),
                html=args.get("html"),
                lesson_id=_int_arg(args, "lernumgebung_id"),
                base=base,
            )
            return f"Lernumgebung {data['id']} aktualisiert.\nZum Ansehen/Testen: {data['teacher_url']}"
    except ApiError as exc:
        raise ToolError(exc.message)
    raise ToolError(f"Unbekanntes Werkzeug: {name}")


# --------------------------------------------------------------------------
# JSON-RPC
# --------------------------------------------------------------------------

def _result(msg_id, result):
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _error(msg_id, code, message):
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def _handle(teacher, msg, base):
    """Handle one JSON-RPC message; return a response dict or None (no reply)."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        return _error(None, -32600, "Invalid Request")
    if "method" not in msg:
        return None  # a response/ack from the client: nothing to answer
    method = msg["method"]
    msg_id = msg.get("id")
    params = msg.get("params") or {}
    if msg_id is None:
        return None  # notification (e.g. notifications/initialized)

    if method == "initialize":
        requested = params.get("protocolVersion")
        version = requested if requested in PROTOCOL_VERSIONS else LATEST_PROTOCOL
        return _result(
            msg_id,
            {
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
                "instructions": INSTRUCTIONS,
            },
        )
    if method == "ping":
        return _result(msg_id, {})
    if method == "tools/list":
        return _result(msg_id, {"tools": TOOLS})
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        if not isinstance(args, dict):
            return _error(msg_id, -32602, "'arguments' muss ein Objekt sein.")
        try:
            text = _call_tool(teacher, name, args, base)
        except ToolError as exc:
            return _result(msg_id, {"content": [{"type": "text", "text": str(exc)}], "isError": True})
        return _result(msg_id, {"content": [{"type": "text", "text": text}]})
    if method == "resources/list":
        return _result(msg_id, {"resources": []})
    if method == "prompts/list":
        return _result(msg_id, {"prompts": []})
    return _error(msg_id, -32601, f"Method not found: {method}")


def _bearer(request):
    auth = request.headers.get("Authorization", "")
    return auth[7:].strip() if auth.lower().startswith("bearer ") else ""


@csrf_exempt
@require_http_methods(["GET", "POST", "DELETE"])
def mcp_endpoint(request, key=None):
    teacher = teacher_for_key(key or _bearer(request))
    if teacher is None:
        response = JsonResponse({"error": "Ungültiger oder fehlender API-Schlüssel."}, status=401)
        response["WWW-Authenticate"] = 'Bearer realm="schulplattform"'
        return response

    if request.method != "POST":
        # No server-initiated event stream and no sessions: both optional.
        return HttpResponse(status=405, headers={"Allow": "POST"})

    try:
        payload = json.loads(request.body or "")
    except ValueError:
        return JsonResponse(_error(None, -32700, "Parse error"), status=400)

    base = request.build_absolute_uri("/").rstrip("/")
    if isinstance(payload, list):  # JSON-RPC batch (older protocol revisions)
        replies = [r for r in (_handle(teacher, m, base) for m in payload) if r is not None]
        if not replies:
            return HttpResponse(status=202)
        return JsonResponse(replies, safe=False)

    reply = _handle(teacher, payload, base)
    if reply is None:
        return HttpResponse(status=202)
    return JsonResponse(reply)

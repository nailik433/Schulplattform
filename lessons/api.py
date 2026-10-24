"""HTTP API for creating learning environments from an external assistant
(e.g. a Claude chat). Authenticated with an API key sent as the
``X-API-Key`` header (or ``Authorization: Bearer <key>``).

The service functions (``classes_data``, ``lessons_data``, ``upsert_lesson``)
are shared with the remote MCP endpoint in :mod:`lessons.mcp`, so both
entry points behave identically."""

import json

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from schools.models import SchoolClass

from .models import ApiKey, Lesson
from .protocol import check_protocol


class ApiError(Exception):
    """A request error with an HTTP status and a message for the caller."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------

def teacher_for_key(key):
    """Return the teacher owning an active API key, or None."""
    key = (key or "").strip()
    if not key:
        return None
    api_key = ApiKey.objects.filter(key=key, is_active=True).select_related("teacher").first()
    if api_key is None:
        return None
    api_key.last_used_at = timezone.now()
    api_key.save(update_fields=["last_used_at"])
    return api_key.teacher


def _get_api_teacher(request):
    key = request.headers.get("X-API-Key", "")
    if not key:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            key = auth[7:].strip()
    return teacher_for_key(key)


def teacher_classes(teacher):
    return SchoolClass.objects.filter(memberships__teacher=teacher).distinct()


# --------------------------------------------------------------------------
# Service functions (shared with the MCP endpoint)
# --------------------------------------------------------------------------

def classes_data(teacher):
    return [
        {
            "id": c.id,
            "name": c.name,
            "subject": c.subject,
            "school": c.school.name,
            "students": c.active_student_count(),
        }
        for c in teacher_classes(teacher).select_related("school")
    ]


def _lesson_data(lesson, base):
    return {
        "id": lesson.id,
        "title": lesson.title,
        "class_id": lesson.school_class_id,
        "class_name": lesson.school_class.name,
        "updated_at": lesson.updated_at.isoformat(timespec="minutes"),
        "teacher_url": f"{base}{lesson.get_absolute_url()}",
    }


def _with_hints(data, html):
    """Attach what the HTML forgot to report to the platform, so whoever (or
    whatever assistant) uploaded the lesson learns about it right away."""
    data["hinweise"] = check_protocol(html)
    return data


def lessons_data(teacher, class_id=None, base=""):
    classes = teacher_classes(teacher)
    lessons = Lesson.objects.filter(school_class__in=classes).select_related("school_class")
    if class_id is not None:
        if not classes.filter(id=class_id).exists():
            raise ApiError(
                "'class_id' ungültig oder keine Berechtigung. "
                "Verfügbare Klassen unter GET /api/classes."
            )
        lessons = lessons.filter(school_class_id=class_id)
    return [_lesson_data(lesson, base) for lesson in lessons]


def upsert_lesson(teacher, *, title, html, class_id=None, lesson_id=None, base=""):
    """Create a lesson in one of the teacher's classes, or replace title and
    HTML of an existing one. Returns ``(data, created)``."""
    title = (title or "").strip()
    html = html or ""
    if not title:
        raise ApiError("'title' fehlt.")
    if not html.strip():
        raise ApiError("'html' fehlt.")

    classes = teacher_classes(teacher)
    if lesson_id:
        lesson = (
            Lesson.objects.filter(id=lesson_id, school_class__in=classes)
            .select_related("school_class")
            .first()
        )
        if lesson is None:
            raise ApiError("Lernumgebung nicht gefunden.", status=404)
        lesson.title = title
        lesson.html = html
        lesson.save()
        return _with_hints(_lesson_data(lesson, base), html), False

    school_class = classes.filter(id=class_id).first()
    if school_class is None:
        raise ApiError(
            "'class_id' ungültig oder keine Berechtigung. "
            "Verfügbare Klassen unter GET /api/classes."
        )
    lesson = Lesson.objects.create(
        school_class=school_class, title=title, html=html, created_by=teacher
    )
    return _with_hints(_lesson_data(lesson, base), html), True


# --------------------------------------------------------------------------
# Views
# --------------------------------------------------------------------------

def _unauthorized():
    return JsonResponse({"error": "Ungültiger oder fehlender API-Schlüssel."}, status=401)


@require_GET
@csrf_exempt
def api_classes(request):
    """GET /api/classes — list the key owner's classes."""
    teacher = _get_api_teacher(request)
    if teacher is None:
        return _unauthorized()
    return JsonResponse({"classes": classes_data(teacher)})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_lessons(request):
    """GET  /api/lessons[?class_id=] — list learning environments.
    POST /api/lessons — create (or update) one.

    POST body: {"class_id": int, "title": str, "html": str, "id": int?}
    """
    teacher = _get_api_teacher(request)
    if teacher is None:
        return _unauthorized()
    base = request.build_absolute_uri("/").rstrip("/")

    if request.method == "GET":
        raw = request.GET.get("class_id")
        try:
            class_id = int(raw) if raw else None
        except ValueError:
            return JsonResponse({"error": "'class_id' muss eine Zahl sein."}, status=400)
        try:
            return JsonResponse({"lessons": lessons_data(teacher, class_id, base)})
        except ApiError as exc:
            return JsonResponse({"error": exc.message}, status=exc.status)

    try:
        body = json.loads(request.body or "{}")
    except ValueError:
        return JsonResponse({"error": "Ungültiges JSON."}, status=400)
    try:
        data, created = upsert_lesson(
            teacher,
            title=body.get("title"),
            html=body.get("html"),
            class_id=body.get("class_id"),
            lesson_id=body.get("id"),
            base=base,
        )
    except ApiError as exc:
        return JsonResponse({"error": exc.message}, status=exc.status)
    return JsonResponse(data, status=201 if created else 200)

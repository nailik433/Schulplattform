"""HTTP API for creating learning environments from an external assistant
(e.g. a Claude chat). Authenticated with an API key sent as the
``X-API-Key`` header (or ``Authorization: Bearer <key>``)."""

import json

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from schools.models import SchoolClass

from .models import ApiKey, Lesson


def _get_api_teacher(request):
    key = request.headers.get("X-API-Key", "")
    if not key:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            key = auth[7:].strip()
    if not key:
        return None
    api_key = ApiKey.objects.filter(key=key, is_active=True).select_related("teacher").first()
    if api_key is None:
        return None
    api_key.last_used_at = timezone.now()
    api_key.save(update_fields=["last_used_at"])
    return api_key.teacher


def _teacher_classes(teacher):
    return SchoolClass.objects.filter(memberships__teacher=teacher).distinct()


@require_GET
@csrf_exempt
def api_classes(request):
    """GET /api/classes — list the key owner's classes."""
    teacher = _get_api_teacher(request)
    if teacher is None:
        return JsonResponse({"error": "Ungültiger oder fehlender API-Schlüssel."}, status=401)
    data = [
        {
            "id": c.id,
            "name": c.name,
            "subject": c.subject,
            "school": c.school.name,
            "students": c.active_student_count(),
        }
        for c in _teacher_classes(teacher).select_related("school")
    ]
    return JsonResponse({"classes": data})


@csrf_exempt
@require_POST
def api_lessons(request):
    """POST /api/lessons — create (or update) a learning environment.

    Body: {"class_id": int, "title": str, "html": str, "id": int?}
    """
    teacher = _get_api_teacher(request)
    if teacher is None:
        return JsonResponse({"error": "Ungültiger oder fehlender API-Schlüssel."}, status=401)

    try:
        body = json.loads(request.body or "{}")
    except ValueError:
        return JsonResponse({"error": "Ungültiges JSON."}, status=400)

    title = (body.get("title") or "").strip()
    html = body.get("html") or ""
    class_id = body.get("class_id")
    lesson_id = body.get("id")

    if not title:
        return JsonResponse({"error": "'title' fehlt."}, status=400)
    if not html.strip():
        return JsonResponse({"error": "'html' fehlt."}, status=400)

    classes = _teacher_classes(teacher)

    if lesson_id:
        lesson = Lesson.objects.filter(id=lesson_id, school_class__in=classes).first()
        if lesson is None:
            return JsonResponse({"error": "Lernumgebung nicht gefunden."}, status=404)
        lesson.title = title
        lesson.html = html
        lesson.save()
    else:
        school_class = classes.filter(id=class_id).first()
        if school_class is None:
            return JsonResponse(
                {"error": "'class_id' ungültig oder keine Berechtigung. "
                          "Verfügbare Klassen unter GET /api/classes."},
                status=400,
            )
        lesson = Lesson.objects.create(
            school_class=school_class, title=title, html=html, created_by=teacher
        )

    base = request.build_absolute_uri("/").rstrip("/")
    return JsonResponse(
        {
            "id": lesson.id,
            "title": lesson.title,
            "class_id": lesson.school_class_id,
            "teacher_url": f"{base}{lesson.get_absolute_url()}",
        },
        status=200 if lesson_id else 201,
    )

import json
import math

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from schools.models import ClassMembership, SchoolClass
from schools.views import get_current_student

from .forms import LessonForm
from .models import ApiKey, Lesson, LessonResult, LessonState
from .protocol import LESSON_PROTOCOL


# --------------------------------------------------------------------------
# Access helpers
# --------------------------------------------------------------------------

def _teacher_class_or_404(user, class_pk):
    return get_object_or_404(
        SchoolClass.objects.filter(memberships__teacher=user).distinct(), pk=class_pk
    )


def _row_progress(result, state):
    """0-100 for the teacher's table: finished = 100, otherwise what the lesson
    reported with its last save (``None`` if it reported nothing)."""
    if result is not None and result.completed:
        return 100
    return state.progress if state is not None else None


def _teacher_lesson_or_404(user, pk):
    return get_object_or_404(
        Lesson.objects.filter(school_class__memberships__teacher=user)
        .select_related("school_class")
        .distinct(),
        pk=pk,
    )


# Lesson HTML is authored by teachers or by an AI through the API, i.e. it is
# untrusted code served from our own domain. The CSP ``sandbox`` directive
# gives the document an opaque origin *even when opened directly in a tab*,
# so it can never read the platform's cookies or call teacher endpoints as the
# logged-in user. Our own pages embed it in an iframe with the same sandbox
# attribute; ``xframe_options_sameorigin`` lets exactly those pages do that.
LESSON_CSP = "sandbox allow-scripts allow-forms allow-popups"


# Largest accepted work-in-progress, measured on the compact JSON in bytes.
STATE_MAX_BYTES = 64 * 1024


def _reject_constant(name):
    raise ValueError(f"unzulässiger JSON-Wert: {name}")


def _loads_strict(raw):
    """``json.loads`` that refuses NaN/Infinity (PostgreSQL's jsonb would
    fail on them) and absurdly deep nesting, instead of crashing."""
    try:
        return json.loads(raw, parse_constant=_reject_constant)
    except (ValueError, RecursionError):
        raise ValueError("ungültiges JSON")


def _number(value):
    """A finite number as float, otherwise ``None`` (bools are not numbers)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _progress(value):
    """A progress percentage as int 0-100, otherwise ``None``."""
    number = _number(value)
    if number is None:
        return None
    return max(0, min(100, round(number)))


def _compact_size(value):
    return len(json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _lesson_html_response(html):
    response = HttpResponse(html or "<p>Noch kein Inhalt.</p>")
    response["Content-Security-Policy"] = LESSON_CSP
    return response


# --------------------------------------------------------------------------
# Teacher views
# --------------------------------------------------------------------------

@login_required
def lesson_create(request, class_pk):
    school_class = _teacher_class_or_404(request.user, class_pk)
    if request.method == "POST":
        form = LessonForm(request.POST)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.school_class = school_class
            lesson.created_by = request.user
            lesson.save()
            messages.success(request, f"Lernumgebung „{lesson.title}“ wurde erstellt.")
            return redirect(lesson.get_absolute_url())
    else:
        form = LessonForm()
    return render(
        request,
        "lessons/lesson_form.html",
        {"form": form, "school_class": school_class},
    )


@login_required
def lesson_edit(request, pk):
    lesson = _teacher_lesson_or_404(request.user, pk)
    if request.method == "POST":
        form = LessonForm(request.POST, instance=lesson)
        if form.is_valid():
            form.save()
            messages.success(request, "Lernumgebung aktualisiert.")
            return redirect(lesson.get_absolute_url())
    else:
        form = LessonForm(instance=lesson)
    return render(
        request,
        "lessons/lesson_form.html",
        {"form": form, "school_class": lesson.school_class, "lesson": lesson},
    )


@login_required
def lesson_detail(request, pk):
    lesson = _teacher_lesson_or_404(request.user, pk)
    results = {
        r.student_id: r
        for r in lesson.results.select_related("student")
    }
    states = {s.student_id: s for s in lesson.states.only("student_id", "updated_at", "progress")}
    roster = []
    for student in lesson.school_class.students.filter(is_active=True):
        roster.append(
            {
                "student": student,
                "result": results.get(student.id),
                "state_at": states[student.id].updated_at if student.id in states else None,
                "progress": _row_progress(results.get(student.id), states.get(student.id)),
            }
        )
    done = sum(1 for row in roster if row["result"] and row["result"].completed)
    return render(
        request,
        "lessons/lesson_detail.html",
        {
            "lesson": lesson,
            "roster": roster,
            "done_count": done,
            "roster_count": len(roster),
            "state_count": sum(1 for row in roster if row["state_at"]),
        },
    )


@login_required
@xframe_options_sameorigin
def lesson_preview(request, pk):
    """Serve the lesson's HTML to the teacher for preview (sandboxed, see
    ``_lesson_html_response``)."""
    lesson = _teacher_lesson_or_404(request.user, pk)
    return _lesson_html_response(lesson.html)


@login_required
@require_POST
def lesson_delete(request, pk):
    lesson = _teacher_lesson_or_404(request.user, pk)
    school_class = lesson.school_class
    title = lesson.title
    lesson.delete()
    messages.success(request, f"Lernumgebung „{title}“ wurde gelöscht.")
    return redirect(school_class.get_absolute_url())


def _readable(value):
    if isinstance(value, bool):
        return "ja" if value else "nein"
    if isinstance(value, (str, int, float)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, indent=2)


@login_required
def result_detail(request, pk, student_pk):
    """What one pupil reported for a lesson: points, bonus points, the
    individual results (``detail``) and the raw saved state."""
    lesson = _teacher_lesson_or_404(request.user, pk)
    student = get_object_or_404(lesson.school_class.students, pk=student_pk)
    result = LessonResult.objects.filter(lesson=lesson, student=student).first()
    state = LessonState.objects.filter(lesson=lesson, student=student).first()
    detail = (result.detail if result and isinstance(result.detail, dict) else {}) or {}
    shown = list(detail.items())[:200]
    return render(
        request,
        "lessons/result_detail.html",
        {
            "lesson": lesson,
            "student": student,
            "result": result,
            "state": state,
            "progress": _row_progress(result, state),
            "detail_rows": [(str(key), _readable(value)) for key, value in shown],
            "detail_truncated": len(detail) > len(shown),
            "state_json": json.dumps(state.state, ensure_ascii=False, indent=2) if state else "",
        },
    )


@login_required
@require_POST
def state_reset(request, pk, student_pk):
    """Delete one pupil's saved work-in-progress so they start the lesson over."""
    lesson = _teacher_lesson_or_404(request.user, pk)
    student = get_object_or_404(lesson.school_class.students, pk=student_pk)
    deleted, _ = LessonState.objects.filter(lesson=lesson, student=student).delete()
    if deleted:
        messages.success(request, f"Fortschritt von {student.seat_label or student.label} zurückgesetzt.")
    else:
        messages.info(request, "Es war kein Zwischenstand gespeichert.")
    return redirect(lesson.get_absolute_url())


@login_required
@require_POST
def state_reset_all(request, pk):
    lesson = _teacher_lesson_or_404(request.user, pk)
    deleted, _ = LessonState.objects.filter(lesson=lesson).delete()
    messages.success(request, f"Fortschritt für {deleted} Schüler/innen zurückgesetzt.")
    return redirect(lesson.get_absolute_url())


# --------------------------------------------------------------------------
# Student views
# --------------------------------------------------------------------------

def _student_lesson_or_404(request, pk):
    student = get_current_student(request)
    if student is None:
        return None, None
    lesson = Lesson.objects.filter(
        pk=pk, school_class_id=student.school_class_id
    ).first()
    return student, lesson


@never_cache  # the page embeds the pupil's saved state: never serve a stale copy
def lesson_play(request, pk):
    """Student-facing page: shows the lesson's HTML in a sandboxed iframe.

    The saved work-in-progress is delivered inside the page itself, so it is
    there before the lesson's own script can ask for it (no loading race)."""
    student, lesson = _student_lesson_or_404(request, pk)
    if student is None:
        return redirect("schools:student_login")
    if lesson is None:
        raise Http404
    LessonResult.objects.get_or_create(lesson=lesson, student=student)
    saved = LessonState.objects.filter(lesson=lesson, student=student).first()
    return render(
        request,
        "lessons/lesson_play.html",
        {
            "lesson": lesson,
            "student": student,
            "initial_state": saved.state if saved else None,
        },
    )


@xframe_options_sameorigin
def lesson_content(request, pk):
    """Serve the raw lesson HTML for the student's sandboxed iframe."""
    student, lesson = _student_lesson_or_404(request, pk)
    if student is None or lesson is None:
        raise Http404
    return _lesson_html_response(lesson.html)


@require_POST
def lesson_report(request, pk):
    """Record a result reported by the lesson HTML.

    The sandboxed iframe posts a message to the player page, which forwards
    it here with the regular CSRF token (so no CSRF exemption is needed)."""
    student, lesson = _student_lesson_or_404(request, pk)
    if student is None or lesson is None:
        raise Http404
    try:
        payload = _loads_strict(request.body or "{}")
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    result, _ = LessonResult.objects.get_or_create(lesson=lesson, student=student)
    score = _number(payload.get("score"))
    max_score = _number(payload.get("max") if "max" in payload else payload.get("max_score"))
    if score is not None:
        result.score = score
    if max_score is not None:
        result.max_score = max_score
    extra, extra_max = _number(payload.get("extra")), _number(payload.get("extra_max"))
    if extra is not None:
        result.extra = extra
    if extra_max is not None:
        result.extra_max = extra_max
    result.completed = bool(payload.get("completed", True))
    detail = payload.get("detail")
    if isinstance(detail, dict) and _compact_size(detail) <= STATE_MAX_BYTES:
        result.detail = detail
    result.save()
    return JsonResponse({"ok": True})


@require_POST
def lesson_state_save(request, pk):
    """Store (or clear) the logged-in pupil's work-in-progress for this lesson.

    Only the pupil's own state can be written: the pupil comes from the
    session, never from the request. Body: ``{"state": <JSON>}``, at most
    64 KB; ``{"state": null}`` deletes the saved state. Last write wins."""
    student, lesson = _student_lesson_or_404(request, pk)
    if student is None or lesson is None:
        raise Http404

    try:
        declared = int(request.META.get("CONTENT_LENGTH") or 0)
    except ValueError:
        declared = 0
    if declared > STATE_MAX_BYTES + 1024:  # envelope overhead, checked again below
        return JsonResponse({"ok": False, "error": "too_large"}, status=413)

    try:
        payload = _loads_strict(request.body or "")
    except ValueError:
        return JsonResponse({"ok": False, "error": "invalid_json"}, status=400)
    if not isinstance(payload, dict) or "state" not in payload:
        return JsonResponse({"ok": False, "error": "state_missing"}, status=400)

    state = payload["state"]
    if state is None:
        LessonState.objects.filter(lesson=lesson, student=student).delete()
        return JsonResponse({"ok": True})

    size = len(json.dumps(state, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    if size > STATE_MAX_BYTES:
        return JsonResponse({"ok": False, "error": "too_large"}, status=413)
    defaults = {"state": state}
    progress = _progress(payload.get("progress"))
    if progress is not None:  # a save without progress keeps the last known value
        defaults["progress"] = progress
    LessonState.objects.update_or_create(lesson=lesson, student=student, defaults=defaults)
    return JsonResponse({"ok": True})


# --------------------------------------------------------------------------
# API key management (teacher)
# --------------------------------------------------------------------------

@login_required
def api_key_page(request):
    if request.method == "POST":
        # Regenerate: deactivate old, create a new one.
        request.user.api_keys.update(is_active=False)
        ApiKey.objects.create(teacher=request.user)
        messages.success(request, "Neuer API-Schlüssel erstellt.")
        return redirect("lessons:api_key")
    key = request.user.api_keys.filter(is_active=True).first()
    if key is None:
        key = ApiKey.objects.create(teacher=request.user)
    base = request.build_absolute_uri("/").rstrip("/")
    return render(
        request,
        "lessons/api_key.html",
        {"api_key": key, "base_url": base, "lesson_protocol": LESSON_PROTOCOL},
    )

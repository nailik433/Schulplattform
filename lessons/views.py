import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from schools.models import ClassMembership, SchoolClass
from schools.views import get_current_student

from .forms import LessonForm
from .models import ApiKey, Lesson, LessonResult


# --------------------------------------------------------------------------
# Access helpers
# --------------------------------------------------------------------------

def _teacher_class_or_404(user, class_pk):
    return get_object_or_404(
        SchoolClass.objects.filter(memberships__teacher=user).distinct(), pk=class_pk
    )


def _teacher_lesson_or_404(user, pk):
    return get_object_or_404(
        Lesson.objects.filter(school_class__memberships__teacher=user)
        .select_related("school_class")
        .distinct(),
        pk=pk,
    )


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
    roster = []
    for student in lesson.school_class.students.filter(is_active=True):
        roster.append({"student": student, "result": results.get(student.id)})
    done = sum(1 for row in roster if row["result"] and row["result"].completed)
    return render(
        request,
        "lessons/lesson_detail.html",
        {
            "lesson": lesson,
            "roster": roster,
            "done_count": done,
            "roster_count": len(roster),
        },
    )


@login_required
def lesson_preview(request, pk):
    """Serve the lesson's HTML to the teacher for preview (sandboxed in the
    detail page's iframe)."""
    lesson = _teacher_lesson_or_404(request.user, pk)
    return HttpResponse(lesson.html or "<p>Noch kein Inhalt.</p>")


@login_required
@require_POST
def lesson_delete(request, pk):
    lesson = _teacher_lesson_or_404(request.user, pk)
    school_class = lesson.school_class
    title = lesson.title
    lesson.delete()
    messages.success(request, f"Lernumgebung „{title}“ wurde gelöscht.")
    return redirect(school_class.get_absolute_url())


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


def lesson_play(request, pk):
    """Student-facing page: shows the lesson's HTML in a sandboxed iframe."""
    student, lesson = _student_lesson_or_404(request, pk)
    if student is None:
        return redirect("schools:student_login")
    if lesson is None:
        raise Http404
    LessonResult.objects.get_or_create(lesson=lesson, student=student)
    return render(request, "lessons/lesson_play.html", {"lesson": lesson, "student": student})


def lesson_content(request, pk):
    """Serve the raw lesson HTML for the student's sandboxed iframe."""
    student, lesson = _student_lesson_or_404(request, pk)
    if student is None or lesson is None:
        raise Http404
    return HttpResponse(lesson.html or "<p>Noch kein Inhalt.</p>")


@csrf_exempt
@require_POST
def lesson_report(request, pk):
    """Record a result reported by the lesson HTML (via postMessage -> fetch)."""
    student, lesson = _student_lesson_or_404(request, pk)
    if student is None or lesson is None:
        raise Http404
    try:
        payload = json.loads(request.body or "{}")
    except ValueError:
        payload = {}
    result, _ = LessonResult.objects.get_or_create(lesson=lesson, student=student)
    score = payload.get("score")
    max_score = payload.get("max") if "max" in payload else payload.get("max_score")
    if isinstance(score, (int, float)):
        result.score = float(score)
    if isinstance(max_score, (int, float)):
        result.max_score = float(max_score)
    result.completed = bool(payload.get("completed", True))
    if isinstance(payload.get("detail"), dict):
        result.detail = payload["detail"]
    result.save()
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
    return render(request, "lessons/api_key.html", {"api_key": key, "base_url": base})

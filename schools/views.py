from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import (
    BulkStudentForm,
    CountStudentForm,
    SchoolClassForm,
    StudentForm,
    StudentLoginForm,
)
from .models import ClassMembership, SchoolClass, Student
from .qr import qr_svg

STUDENT_SESSION_KEY = "student_id"

# Brute-force protection for student token login: at most this many failed
# attempts per client IP per hour (like VokaGo's in-memory limiter).
MAX_LOGIN_ATTEMPTS = 10
LOGIN_ATTEMPT_WINDOW = 3600  # seconds


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _teacher_classes(user):
    """Classes the given teacher may access (as owner or collaborator)."""
    return SchoolClass.objects.filter(memberships__teacher=user).distinct()


def _get_teacher_class(user, pk):
    """Fetch a class the teacher is a member of, or 404."""
    return get_object_or_404(_teacher_classes(user), pk=pk)


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _login_attempts_key(request):
    return f"student_login_fail:{_client_ip(request)}"


def _too_many_attempts(request):
    return cache.get(_login_attempts_key(request), 0) >= MAX_LOGIN_ATTEMPTS


def _register_failed_attempt(request):
    key = _login_attempts_key(request)
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, LOGIN_ATTEMPT_WINDOW)


def _reset_attempts(request):
    cache.delete(_login_attempts_key(request))


def _find_active_student(token):
    return (
        Student.objects.filter(access_code__iexact=token, is_active=True)
        .select_related("school_class", "school_class__school")
        .first()
    )


def get_current_student(request):
    """Return the Student for the current student session, or None."""
    student_id = request.session.get(STUDENT_SESSION_KEY)
    if not student_id:
        return None
    return (
        Student.objects.filter(pk=student_id, is_active=True)
        .select_related("school_class", "school_class__school")
        .first()
    )


# --------------------------------------------------------------------------
# Public / landing
# --------------------------------------------------------------------------

def home(request):
    return render(request, "home.html")


# --------------------------------------------------------------------------
# Teacher area
# --------------------------------------------------------------------------

@login_required
def dashboard(request):
    my_classes = _teacher_classes(request.user).select_related("school")
    # Classes the teacher owns in their own school vs. classes shared with them.
    owned = [c for c in my_classes if c.school_id == request.user.school_id]
    shared = [c for c in my_classes if c.school_id != request.user.school_id]
    context = {
        "school": request.user.school,
        "owned_classes": owned,
        "shared_classes": shared,
    }
    return render(request, "schools/dashboard.html", context)


@login_required
def class_create(request):
    school = request.user.school
    if school is None:
        messages.error(
            request,
            "Dir ist noch keine Schule zugeordnet. Bitte wende dich an die "
            "Administration der Plattform.",
        )
        return redirect("schools:dashboard")

    if request.method == "POST":
        form = SchoolClassForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                school_class = form.save(commit=False)
                school_class.school = school
                school_class.save()
                ClassMembership.objects.create(
                    school_class=school_class,
                    teacher=request.user,
                    role=ClassMembership.Role.OWNER,
                )
            messages.success(request, f"Klasse „{school_class}“ wurde angelegt.")
            return redirect(school_class.get_absolute_url())
    else:
        form = SchoolClassForm()
    return render(
        request,
        "schools/class_form.html",
        {"form": form, "school": school},
    )


@login_required
def class_detail(request, pk):
    school_class = _get_teacher_class(request.user, pk)
    students = school_class.students.all()
    context = {
        "school_class": school_class,
        "students": students,
        "student_form": StudentForm(),
        "count_form": CountStudentForm(),
        "bulk_form": BulkStudentForm(),
    }
    return render(request, "schools/class_detail.html", context)


@login_required
@require_POST
def student_add(request, pk):
    school_class = _get_teacher_class(request.user, pk)
    form = StudentForm(request.POST)
    if form.is_valid():
        student = form.save(commit=False)
        student.school_class = school_class
        student.save()
        messages.success(
            request,
            f"{student.label} hinzugefügt. Zugangscode: {student.access_code}",
        )
    else:
        messages.error(request, "Der Schüler/die Schülerin konnte nicht angelegt werden.")
    return redirect(school_class.get_absolute_url())


@login_required
@require_POST
def student_add_count(request, pk):
    school_class = _get_teacher_class(request.user, pk)
    form = CountStudentForm(request.POST)
    if form.is_valid():
        count = form.cleaned_data["count"]
        for _ in range(count):
            Student.objects.create(school_class=school_class)
        messages.success(
            request,
            f"{count} Plätze angelegt. Die Tokens findest du in der Liste – "
            "oder drucke direkt das QR-Dokument.",
        )
    else:
        messages.error(request, "Bitte eine gültige Anzahl (1–60) eingeben.")
    return redirect(school_class.get_absolute_url())


@login_required
@require_POST
def student_bulk_add(request, pk):
    school_class = _get_teacher_class(request.user, pk)
    form = BulkStudentForm(request.POST)
    if form.is_valid():
        names = form.cleaned_data["names"]
        created = [
            Student.objects.create(school_class=school_class, display_name=name)
            for name in names
        ]
        messages.success(
            request,
            f"{len(created)} Schüler/innen hinzugefügt. "
            "Die Tokens findest du in der Liste unten.",
        )
    else:
        messages.error(request, "Bitte mindestens einen Namen eingeben.")
    return redirect(school_class.get_absolute_url())


@login_required
@require_POST
def student_regenerate_code(request, pk, student_pk):
    school_class = _get_teacher_class(request.user, pk)
    student = get_object_or_404(school_class.students, pk=student_pk)
    student.regenerate_access_code()
    messages.success(
        request,
        f"Neuer Zugangscode für {student.label}: {student.access_code}",
    )
    return redirect(school_class.get_absolute_url())


@login_required
@require_POST
def student_toggle_active(request, pk, student_pk):
    school_class = _get_teacher_class(request.user, pk)
    student = get_object_or_404(school_class.students, pk=student_pk)
    student.is_active = not student.is_active
    student.save(update_fields=["is_active"])
    state = "aktiviert" if student.is_active else "deaktiviert"
    messages.success(request, f"{student.label} wurde {state}.")
    return redirect(school_class.get_absolute_url())


@login_required
@require_POST
def student_delete(request, pk, student_pk):
    school_class = _get_teacher_class(request.user, pk)
    student = get_object_or_404(school_class.students, pk=student_pk)
    label = student.label
    student.delete()
    messages.success(request, f"{label} wurde entfernt.")
    return redirect(school_class.get_absolute_url())


@login_required
def class_qr_document(request, pk):
    """Printable A4 document: QR cards (3x5 grid) plus a confidential teacher
    list mapping numbers/tokens to hand-written names."""
    school_class = _get_teacher_class(request.user, pk)
    students = list(school_class.students.filter(is_active=True))

    cards = []
    for student in students:
        url = request.build_absolute_uri(f"/s/{student.access_code}/")
        cards.append({"student": student, "url": url, "svg": qr_svg(url)})

    # Chunk into pages of 15 (a 3x5 grid). Pad the last page with empty cells
    # so its layout stays consistent.
    per_page = 15
    pages = [cards[i : i + per_page] for i in range(0, len(cards), per_page)]
    if pages:
        last = pages[-1]
        pages[-1] = last + [None] * (per_page - len(last))

    context = {
        "school_class": school_class,
        "students": students,
        "pages": pages,
    }
    return render(request, "schools/qr_document.html", context)


# --------------------------------------------------------------------------
# Student area
# --------------------------------------------------------------------------

def student_login(request):
    """Start page where a pupil types their token (or arrives after scanning
    a QR code). On success we redirect to the token URL, which is also what
    the QR code points at."""
    if get_current_student(request):
        return redirect(
            "schools:student_space",
            token=get_current_student(request).access_code,
        )

    if request.method == "POST":
        if _too_many_attempts(request):
            messages.error(
                request,
                "Zu viele Fehlversuche. Bitte versuche es später erneut.",
            )
            return render(request, "students/login.html", {"form": StudentLoginForm()})

        form = StudentLoginForm(request.POST)
        if form.is_valid():
            token = form.cleaned_data["access_code"]
            if _find_active_student(token):
                return redirect("schools:student_space", token=token)
            _register_failed_attempt(request)
            messages.error(
                request,
                "Der Zugangscode ist ungültig oder wurde deaktiviert.",
            )
    else:
        form = StudentLoginForm()
    return render(request, "students/login.html", {"form": form})


def student_space(request, token):
    """The QR-code target: `/s/<token>/`. Logs the pupil in and shows their
    home page."""
    if _too_many_attempts(request):
        return render(
            request,
            "students/login.html",
            {"form": StudentLoginForm(), "rate_limited": True},
            status=429,
        )

    student = _find_active_student(token)
    if not student:
        _register_failed_attempt(request)
        messages.error(
            request, "Der Zugangscode ist ungültig oder wurde deaktiviert."
        )
        return redirect("schools:student_login")

    _reset_attempts(request)
    request.session[STUDENT_SESSION_KEY] = student.pk
    assignments = (
        student.school_class.assignments.all().prefetch_related("files")
    )
    return render(
        request,
        "students/home.html",
        {"student": student, "assignments": assignments},
    )


def student_logout(request):
    request.session.pop(STUDENT_SESSION_KEY, None)
    messages.info(request, "Du wurdest abgemeldet.")
    return redirect("schools:student_login")

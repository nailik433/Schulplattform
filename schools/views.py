from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.throttling import client_ip, is_blocked, register_failure, reset

from .forms import (
    BulkStudentForm,
    ClassDeleteConfirmForm,
    CountStudentForm,
    SchoolClassForm,
    SetTokenForm,
    ShareClassForm,
    StudentForm,
    StudentImportForm,
    StudentLoginForm,
)
from .models import ClassMembership, SchoolClass, Student
from .qr import qr_svg

STUDENT_SESSION_KEY = "student_id"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _teacher_classes(user):
    """Classes the given teacher may access (as owner or collaborator)."""
    return SchoolClass.objects.filter(memberships__teacher=user).distinct()


def _get_teacher_class(user, pk):
    """Fetch a class the teacher is a member of, or 404."""
    return get_object_or_404(_teacher_classes(user), pk=pk)


def _get_owned_class(user, pk):
    """Fetch a class the teacher OWNS (may manage sharing), or 404."""
    return get_object_or_404(
        SchoolClass.objects.filter(
            memberships__teacher=user,
            memberships__role=ClassMembership.Role.OWNER,
        ),
        pk=pk,
    )


def _is_owner(user, school_class):
    return school_class.memberships.filter(
        teacher=user, role=ClassMembership.Role.OWNER
    ).exists()


# Brute-force protection for the student token login: failed attempts are
# counted per client IP (shared limiter, see accounts.throttling).
def _login_attempts_key(request):
    return f"student_login_fail:{client_ip(request)}"


def _too_many_attempts(request):
    return is_blocked(_login_attempts_key(request))


def _register_failed_attempt(request):
    register_failure(_login_attempts_key(request))


def _reset_attempts(request):
    reset(_login_attempts_key(request))


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
    """The landing page is the student code login. Teachers who are already
    signed in go to their dashboard; a student with an active session goes to
    their space."""
    if request.user.is_authenticated:
        return redirect("schools:dashboard")
    if get_current_student(request):
        return redirect("schools:student_home")
    return render(request, "students/login.html", {"form": StudentLoginForm()})


# --------------------------------------------------------------------------
# Teacher area
# --------------------------------------------------------------------------

@login_required
def dashboard(request):
    my_classes = (
        _teacher_classes(request.user)
        .select_related("school")
        .annotate(
            n_students=Count("students", filter=Q(students__is_active=True), distinct=True),
            n_assignments=Count("assignments", distinct=True),
            n_lessons=Count("lessons", distinct=True),
        )
    )
    # "Own" vs. "shared with me" is a question of the teacher's *role* in the
    # class, not of the school: colleagues at the same school share classes.
    owned_ids = set(
        ClassMembership.objects.filter(
            teacher=request.user, role=ClassMembership.Role.OWNER
        ).values_list("school_class_id", flat=True)
    )
    owned = [c for c in my_classes if c.id in owned_ids]
    shared = [c for c in my_classes if c.id not in owned_ids]
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
    students = list(school_class.students.all())
    assignments = school_class.assignments.annotate(
        n_files=Count("files", distinct=True),
        n_submissions=Count("submissions", distinct=True),
    )
    lessons = school_class.lessons.annotate(
        n_done=Count("results", filter=Q(results__completed=True), distinct=True)
    )
    memberships = school_class.memberships.select_related("teacher")
    owner_membership = next(
        (m for m in memberships if m.role == ClassMembership.Role.OWNER), None
    )
    collaborators = [
        m for m in memberships if m.role == ClassMembership.Role.COLLABORATOR
    ]
    context = {
        "school_class": school_class,
        "students": students,
        "active_count": sum(1 for s in students if s.is_active),
        "assignments": assignments,
        "lessons": lessons,
        "student_form": StudentForm(),
        "count_form": CountStudentForm(),
        "bulk_form": BulkStudentForm(),
        "import_form": StudentImportForm(),
        "is_owner": _is_owner(request.user, school_class),
        "owner": owner_membership.teacher if owner_membership else None,
        "collaborators": collaborators,
        "share_form": ShareClassForm(),
    }
    return render(request, "schools/class_detail.html", context)


@login_required
@require_POST
def class_share_add(request, pk):
    school_class = _get_owned_class(request.user, pk)
    form = ShareClassForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Bitte eine gültige E-Mail-Adresse eingeben.")
        return redirect(school_class.get_absolute_url())

    email = form.cleaned_data["email"]
    User = get_user_model()
    colleague = User.objects.filter(email__iexact=email).first()

    if colleague is None:
        messages.error(
            request,
            "Es gibt kein Konto mit dieser E-Mail. Die Person muss sich zuerst "
            "auf der Plattform registrieren.",
        )
    elif colleague == request.user:
        messages.error(request, "Du bist bereits Inhaber/in dieser Klasse.")
    elif colleague.school_id != school_class.school_id:
        messages.error(
            request, "Diese Person gehört zu einer anderen Schule."
        )
    elif ClassMembership.objects.filter(
        school_class=school_class, teacher=colleague
    ).exists():
        messages.error(request, "Diese Person hat bereits Zugriff auf die Klasse.")
    else:
        ClassMembership.objects.create(
            school_class=school_class,
            teacher=colleague,
            role=ClassMembership.Role.COLLABORATOR,
        )
        messages.success(
            request,
            f"Klasse für {colleague.get_full_name() or colleague.email} freigegeben.",
        )
    return redirect(school_class.get_absolute_url())


@login_required
@require_POST
def class_share_remove(request, pk, teacher_pk):
    school_class = _get_owned_class(request.user, pk)
    membership = get_object_or_404(
        ClassMembership,
        school_class=school_class,
        teacher_id=teacher_pk,
        role=ClassMembership.Role.COLLABORATOR,
    )
    name = membership.teacher.get_full_name() or membership.teacher.email
    membership.delete()
    messages.success(request, f"Freigabe für {name} wurde entfernt.")
    return redirect(school_class.get_absolute_url())


@login_required
def class_delete(request, pk):
    """Delete a whole class (owner only) after typing "löschen" to confirm.
    Removes students, worksheets, submissions and their uploaded files."""
    school_class = _get_owned_class(request.user, pk)

    if request.method == "POST":
        form = ClassDeleteConfirmForm(request.POST)
        if form.is_valid():
            # Remove uploaded file blobs first (DB cascade won't delete them).
            from worksheets.models import AssignmentFile, SubmissionFile

            for af in AssignmentFile.objects.filter(
                assignment__school_class=school_class
            ):
                af.file.delete(save=False)
            for sf in SubmissionFile.objects.filter(
                submission__assignment__school_class=school_class
            ):
                sf.file.delete(save=False)

            name = str(school_class)
            school_class.delete()
            messages.success(request, f"Klasse „{name}“ wurde vollständig gelöscht.")
            return redirect("schools:dashboard")
    else:
        form = ClassDeleteConfirmForm()

    return render(
        request,
        "schools/class_confirm_delete.html",
        {
            "school_class": school_class,
            "form": form,
            "student_count": school_class.students.count(),
            "assignment_count": school_class.assignments.count(),
        },
    )


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
@require_POST
def student_bulk_delete(request, pk):
    school_class = _get_teacher_class(request.user, pk)
    ids = request.POST.getlist("student_ids")
    if not ids:
        messages.error(request, "Es wurde niemand ausgewählt.")
        return redirect(school_class.get_absolute_url())
    qs = school_class.students.filter(pk__in=ids)
    count = qs.count()
    qs.delete()
    messages.success(request, f"{count} Schüler/in(nen) wurden entfernt.")
    return redirect(school_class.get_absolute_url())


@login_required
@require_POST
def student_import(request, pk):
    """Import students with existing tokens (e.g. a pasted Fobizz list)."""
    school_class = _get_teacher_class(request.user, pk)
    form = StudentImportForm(request.POST)
    if not form.is_valid():
        for err in form.errors.get("data", ["Import fehlgeschlagen."]):
            messages.error(request, err)
        return redirect(school_class.get_absolute_url())

    created, skipped = 0, []
    for label, token in form.cleaned_data["data"]:
        if Student.objects.filter(access_code__iexact=token).exists():
            skipped.append(token)
            continue
        Student.objects.create(
            school_class=school_class, display_name=label, access_code=token
        )
        created += 1
    msg = f"{created} Schüler/in(nen) importiert."
    if skipped:
        shown = ", ".join(skipped[:10]) + ("…" if len(skipped) > 10 else "")
        msg += f" {len(skipped)} übersprungen (Token schon vergeben): {shown}"
    messages.success(request, msg)
    return redirect(school_class.get_absolute_url())


@login_required
@require_POST
def student_set_token(request, pk, student_pk):
    school_class = _get_teacher_class(request.user, pk)
    student = get_object_or_404(school_class.students, pk=student_pk)
    form = SetTokenForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Ungültiger Token (3–16 Kleinbuchstaben/Ziffern).")
        return redirect(school_class.get_absolute_url())
    token = form.cleaned_data["token"]
    if Student.objects.filter(access_code__iexact=token).exclude(pk=student.pk).exists():
        messages.error(request, f"Token „{token}“ ist schon vergeben.")
    else:
        student.access_code = token
        student.save(update_fields=["access_code"])
        messages.success(request, f"Neuer Token für {student.seat_label or student.label}: {token}")
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

    # Chunk into pages of 31 (a 4-column grid, up to 8 rows) so a class fits
    # on one A4 page without overlapping.
    per_page = 31
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
        return redirect("schools:student_home")

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
    """The QR-code target: `/s/<token>/`. Logs the pupil in and sends them to
    their start page.

    The token never stays in the address bar: after the redirect it is gone
    from the screen, the browser history and any shared screen; the session
    (not the URL) carries the login from here on.
    """
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
    # New session id on login (no fixation), and a session that ends with the
    # school day so the next pupil on a shared iPad starts fresh.
    request.session.cycle_key()
    request.session[STUDENT_SESSION_KEY] = student.pk
    request.session.set_expiry(settings.STUDENT_SESSION_AGE)
    return redirect("schools:student_home")


def student_home(request):
    """Start page of a logged-in pupil: lessons and worksheets, each with a
    clear status (open / due soon / overdue / done)."""
    student = get_current_student(request)
    if student is None:
        return redirect("schools:student_login")

    now = timezone.now()
    assignments = student.school_class.assignments.all().prefetch_related("files")
    my_subs = {
        s.assignment_id: s
        for s in student.submissions.select_related("assignment").prefetch_related("files")
    }
    rows, open_count = [], 0
    for a in assignments:
        sub = my_subs.get(a.id)
        if not a.collect_submissions:
            status = "material"
        elif sub:
            status = "late" if sub.is_late else "done"
        elif a.due_date and a.due_date < now:
            status = "overdue"
        elif a.due_date and a.due_date - now < timedelta(hours=48):
            status = "soon"
        else:
            status = "open"
        if status in ("open", "soon", "overdue"):
            open_count += 1
        rows.append({"assignment": a, "submission": sub, "status": status})
    # Urgent things first: overdue, due soon, open; then done; material last.
    priority = {"overdue": 0, "soon": 1, "open": 2, "late": 3, "done": 3, "material": 4}
    rows.sort(key=lambda row: priority[row["status"]])

    results = {r.lesson_id: r for r in student.lesson_results.all()}
    lesson_rows = []
    for lesson in student.school_class.lessons.all():
        result = results.get(lesson.id)
        if not (result and result.completed):
            open_count += 1
        lesson_rows.append({"lesson": lesson, "result": result})
    lesson_rows.sort(key=lambda row: bool(row["result"] and row["result"].completed))

    return render(
        request,
        "students/home.html",
        {
            "student": student,
            "rows": rows,
            "lesson_rows": lesson_rows,
            "open_count": open_count,
        },
    )


def student_logout(request):
    request.session.pop(STUDENT_SESSION_KEY, None)
    messages.info(request, "Du wurdest abgemeldet.")
    return redirect("schools:student_login")

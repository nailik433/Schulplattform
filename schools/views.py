from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import (
    BulkStudentForm,
    SchoolClassForm,
    SchoolForm,
    StudentForm,
    StudentLoginForm,
)
from .models import ClassMembership, School, SchoolClass, Student

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
    schools = (
        School.objects.filter(classes__memberships__teacher=request.user)
        .distinct()
        .prefetch_related("classes")
    )
    my_classes = _teacher_classes(request.user).select_related("school")
    context = {
        "schools": schools,
        "classes": my_classes,
    }
    return render(request, "schools/dashboard.html", context)


@login_required
def school_create(request):
    if request.method == "POST":
        form = SchoolForm(request.POST)
        if form.is_valid():
            school = form.save(commit=False)
            school.created_by = request.user
            school.save()
            messages.success(request, f"Schule „{school.name}“ wurde angelegt.")
            return redirect("schools:dashboard")
    else:
        form = SchoolForm()
    return render(
        request,
        "schools/school_form.html",
        {"form": form},
    )


@login_required
def class_create(request, school_pk):
    # Only schools the teacher has access to (created, or has a class in).
    school = get_object_or_404(School, pk=school_pk)
    if school.created_by_id != request.user.id and not _teacher_classes(
        request.user
    ).filter(school=school).exists():
        raise Http404

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
            f"„{student.display_name}“ hinzugefügt. Zugangscode: {student.access_code}",
        )
    else:
        messages.error(request, "Bitte einen gültigen Namen eingeben.")
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
            "Die Zugangscodes findest du in der Liste unten.",
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
        f"Neuer Zugangscode für „{student.display_name}“: {student.access_code}",
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
    messages.success(request, f"„{student.display_name}“ wurde {state}.")
    return redirect(school_class.get_absolute_url())


@login_required
@require_POST
def student_delete(request, pk, student_pk):
    school_class = _get_teacher_class(request.user, pk)
    student = get_object_or_404(school_class.students, pk=student_pk)
    name = student.display_name
    student.delete()
    messages.success(request, f"„{name}“ wurde entfernt.")
    return redirect(school_class.get_absolute_url())


# --------------------------------------------------------------------------
# Student area
# --------------------------------------------------------------------------

def student_login(request):
    # Already logged in as a student? Go to their home.
    if get_current_student(request):
        return redirect("schools:student_home")

    if request.method == "POST":
        form = StudentLoginForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data["access_code"]
            student = Student.objects.filter(
                access_code=code, is_active=True
            ).first()
            if student:
                request.session[STUDENT_SESSION_KEY] = student.pk
                messages.success(request, f"Hallo {student.display_name}!")
                return redirect("schools:student_home")
            messages.error(
                request,
                "Der Zugangscode ist ungültig oder wurde deaktiviert.",
            )
    else:
        form = StudentLoginForm()
    return render(request, "students/login.html", {"form": form})


def student_logout(request):
    request.session.pop(STUDENT_SESSION_KEY, None)
    messages.info(request, "Du wurdest abgemeldet.")
    return redirect("schools:student_login")


def student_home(request):
    student = get_current_student(request)
    if not student:
        return redirect("schools:student_login")
    return render(request, "students/home.html", {"student": student})

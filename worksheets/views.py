import io
import re
import zipfile

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from schools.models import ClassMembership, SchoolClass
from schools.views import get_current_student

from .forms import AssignmentForm, SubmissionForm
from .models import Assignment, AssignmentFile, Submission, SubmissionFile


# --------------------------------------------------------------------------
# Access helpers
# --------------------------------------------------------------------------

def _teacher_class_or_404(user, class_pk):
    return get_object_or_404(
        SchoolClass.objects.filter(memberships__teacher=user).distinct(),
        pk=class_pk,
    )


def _teacher_assignment_or_404(user, pk):
    return get_object_or_404(
        Assignment.objects.filter(
            school_class__memberships__teacher=user
        ).select_related("school_class").distinct(),
        pk=pk,
    )


def _may_access_class(request, school_class):
    """Return 'teacher', 'student' or None for the current visitor."""
    user = request.user
    if user.is_authenticated and ClassMembership.objects.filter(
        school_class=school_class, teacher=user
    ).exists():
        return "teacher"
    student = get_current_student(request)
    if student and student.school_class_id == school_class.id:
        return "student"
    return None


def _save_uploaded_files(assignment, files):
    for upload in files:
        if upload:
            AssignmentFile.objects.create(assignment=assignment, file=upload)


def _safe_name(value):
    """Make a string safe to use inside a ZIP entry or download filename.

    Keeps letters, digits, umlauts and a few harmless separators; removes
    path separators and control characters so a crafted original filename
    can never escape its folder in the archive.
    """
    value = (value or "").strip().replace("/", "-").replace("\\", "-")
    value = re.sub(r"[\x00-\x1f]", "", value)
    value = re.sub(r"[^0-9A-Za-zäöüÄÖÜß ._-]", "_", value)
    return value.strip(" .") or "datei"


# --------------------------------------------------------------------------
# Teacher views
# --------------------------------------------------------------------------

@login_required
def assignment_create(request, class_pk):
    school_class = _teacher_class_or_404(request.user, class_pk)
    if request.method == "POST":
        form = AssignmentForm(request.POST, request.FILES)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.school_class = school_class
            assignment.created_by = request.user
            assignment.save()
            _save_uploaded_files(assignment, form.cleaned_data["files"])
            messages.success(request, f"Arbeitsblatt „{assignment.title}“ wurde ausgeteilt.")
            return redirect(assignment.get_absolute_url())
    else:
        form = AssignmentForm()
    return render(
        request,
        "worksheets/assignment_form.html",
        {"form": form, "school_class": school_class},
    )


@login_required
def assignment_detail(request, pk):
    assignment = _teacher_assignment_or_404(request.user, pk)

    # Build the submission overview: every active student and their submission.
    submissions = {
        s.student_id: s
        for s in assignment.submissions.select_related("student").prefetch_related(
            "files"
        )
    }
    roster = []
    for student in assignment.school_class.students.filter(is_active=True):
        roster.append({"student": student, "submission": submissions.get(student.id)})

    submitted_count = sum(1 for row in roster if row["submission"])

    return render(
        request,
        "worksheets/assignment_detail.html",
        {
            "assignment": assignment,
            "files": assignment.files.all(),
            "roster": roster,
            "submitted_count": submitted_count,
            "roster_count": len(roster),
        },
    )


@login_required
def assignment_edit(request, pk):
    assignment = _teacher_assignment_or_404(request.user, pk)
    if request.method == "POST":
        form = AssignmentForm(request.POST, request.FILES, instance=assignment)
        if form.is_valid():
            form.save()
            _save_uploaded_files(assignment, form.cleaned_data["files"])
            messages.success(request, "Arbeitsblatt aktualisiert.")
            return redirect(assignment.get_absolute_url())
    else:
        form = AssignmentForm(instance=assignment)
    return render(
        request,
        "worksheets/assignment_form.html",
        {"form": form, "school_class": assignment.school_class, "assignment": assignment},
    )


@login_required
@require_POST
def assignment_delete(request, pk):
    assignment = _teacher_assignment_or_404(request.user, pk)
    school_class = assignment.school_class
    # Remove the stored file blobs, then the records.
    for af in assignment.files.all():
        af.file.delete(save=False)
    title = assignment.title
    assignment.delete()
    messages.success(request, f"Arbeitsblatt „{title}“ wurde gelöscht.")
    return redirect(school_class.get_absolute_url())


@login_required
def submissions_zip(request, pk):
    """Download every submitted file of an assignment as one ZIP.

    Each student's files land in their own folder named by the anonymous
    seat label (e.g. ``7b-001/``), so the archive can be handed straight to
    a grading workflow without exposing names. Only teachers of the class
    may download it.
    """
    assignment = _teacher_assignment_or_404(request.user, pk)
    submissions = (
        assignment.submissions.select_related("student")
        .prefetch_related("files")
        .order_by("student__number")
    )

    buffer = io.BytesIO()
    file_count = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for submission in submissions:
            student = submission.student
            folder = _safe_name(
                student.seat_label or f"schueler-{student.number or student.id}"
            )
            used = set()
            for sf in submission.files.all():
                try:
                    handle = sf.file.open("rb")
                except FileNotFoundError:
                    continue
                try:
                    data = handle.read()
                finally:
                    handle.close()
                name = _safe_name(sf.original_name)
                arcname = f"{folder}/{name}"
                counter = 1
                while arcname in used:
                    stem, dot, ext = name.rpartition(".")
                    if dot:
                        arcname = f"{folder}/{stem}_{counter}.{ext}"
                    else:
                        arcname = f"{folder}/{name}_{counter}"
                    counter += 1
                used.add(arcname)
                zf.writestr(arcname, data)
                file_count += 1

    if file_count == 0:
        messages.info(
            request, "Es gibt noch keine abgegebenen Dateien zum Herunterladen."
        )
        return redirect(assignment.get_absolute_url())

    buffer.seek(0)
    stem = slugify(f"{assignment.school_class.name}-{assignment.title}") or "abgaben"
    zip_name = f"{stem}-abgaben.zip"
    response = HttpResponse(buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{zip_name}"'
    return response


@login_required
@require_POST
def file_delete(request, file_pk):
    af = get_object_or_404(
        AssignmentFile.objects.filter(
            assignment__school_class__memberships__teacher=request.user
        ).select_related("assignment"),
        pk=file_pk,
    )
    assignment = af.assignment
    af.file.delete(save=False)
    af.delete()
    messages.success(request, "Datei entfernt.")
    return redirect(assignment.get_absolute_url())


# --------------------------------------------------------------------------
# Download (teachers of the class AND its students)
# --------------------------------------------------------------------------

def file_download(request, file_pk):
    af = get_object_or_404(
        AssignmentFile.objects.select_related("assignment__school_class"), pk=file_pk
    )
    if not _may_access_class(request, af.assignment.school_class):
        raise Http404
    try:
        handle = af.file.open("rb")
    except FileNotFoundError:
        raise Http404
    return FileResponse(handle, as_attachment=True, filename=af.original_name)


# --------------------------------------------------------------------------
# Submissions (student uploads)
# --------------------------------------------------------------------------

def _redirect_student_home(student):
    return redirect("schools:student_home")


@require_POST
def submission_upload(request, assignment_pk):
    student = get_current_student(request)
    if student is None:
        return redirect("schools:student_login")

    assignment = get_object_or_404(
        Assignment.objects.select_related("school_class"), pk=assignment_pk
    )
    # A student may only submit to assignments of their own class that collect
    # submissions.
    if (
        assignment.school_class_id != student.school_class_id
        or not assignment.collect_submissions
    ):
        raise Http404

    form = SubmissionForm(request.POST, request.FILES)
    if form.is_valid():
        submission, _ = Submission.objects.get_or_create(
            assignment=assignment, student=student
        )
        for upload in form.cleaned_data["files"]:
            if upload:
                SubmissionFile.objects.create(submission=submission, file=upload)
        # Touch updated_at so the "late" check reflects the latest upload.
        submission.save(update_fields=["updated_at"])
        messages.success(request, "Deine Abgabe wurde hochgeladen. 👍")
    else:
        messages.error(
            request, "Upload fehlgeschlagen (Datei zu groß oder leer?)."
        )
    return _redirect_student_home(student)


@require_POST
def submission_file_delete(request, file_pk):
    student = get_current_student(request)
    if student is None:
        return redirect("schools:student_login")

    sf = get_object_or_404(
        SubmissionFile.objects.select_related("submission"),
        pk=file_pk,
        submission__student=student,
    )
    sf.file.delete(save=False)
    sf.delete()
    messages.success(request, "Datei aus deiner Abgabe entfernt.")
    return _redirect_student_home(student)


def submission_file_download(request, file_pk):
    sf = get_object_or_404(
        SubmissionFile.objects.select_related(
            "submission__assignment__school_class", "submission__student"
        ),
        pk=file_pk,
    )
    school_class = sf.submission.assignment.school_class
    role = _may_access_class(request, school_class)
    allowed = False
    if role == "teacher":
        allowed = True
    elif role == "student":
        student = get_current_student(request)
        allowed = student and student.id == sf.submission.student_id
    if not allowed:
        raise Http404

    try:
        handle = sf.file.open("rb")
    except FileNotFoundError:
        raise Http404
    return FileResponse(handle, as_attachment=True, filename=sf.original_name)

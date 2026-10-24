import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse

# Maximum size for a single uploaded file (worksheet). 25 MB is plenty for
# PDFs and images while preventing accidental huge uploads.
MAX_UPLOAD_SIZE = 25 * 1024 * 1024


def worksheet_upload_path(instance, filename):
    """Store worksheet files under an unguessable path per class.

    The random folder means the raw MEDIA path cannot be guessed; downloads
    always go through the access-checked view anyway.
    """
    class_id = instance.assignment.school_class_id
    return f"worksheets/class_{class_id}/{uuid.uuid4().hex}/{filename}"


class Assignment(models.Model):
    """A worksheet handed out to a class."""

    school_class = models.ForeignKey(
        "schools.SchoolClass",
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    title = models.CharField("Titel", max_length=200)
    description = models.TextField("Beschreibung / Aufgabe", blank=True)
    due_date = models.DateTimeField("Abgabe bis", null=True, blank=True)
    collect_submissions = models.BooleanField(
        "Abgaben einsammeln",
        default=True,
        help_text="Wenn aktiv, können Schüler/innen eine Lösung hochladen.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignments_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Arbeitsblatt"
        verbose_name_plural = "Arbeitsblätter"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("worksheets:assignment_detail", args=[self.pk])


class AssignmentFile(models.Model):
    """A file attached to an assignment (the worksheet itself)."""

    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name="files",
    )
    file = models.FileField(upload_to=worksheet_upload_path)
    original_name = models.CharField(max_length=255)
    size = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Arbeitsblatt-Datei"
        verbose_name_plural = "Arbeitsblatt-Dateien"
        ordering = ["original_name"]

    def __str__(self):
        return self.original_name

    def save(self, *args, **kwargs):
        if self.file and not self.original_name:
            self.original_name = self.file.name.rsplit("/", 1)[-1]
        if self.file and not self.size:
            self.size = self.file.size
        super().save(*args, **kwargs)

    def get_download_url(self):
        return reverse("worksheets:file_download", args=[self.pk])


def submission_upload_path(instance, filename):
    """Store a submission file under an unguessable per-student path."""
    submission = instance.submission
    return (
        f"submissions/class_{submission.assignment.school_class_id}"
        f"/assignment_{submission.assignment_id}"
        f"/student_{submission.student_id}/{uuid.uuid4().hex}/{filename}"
    )


class Submission(models.Model):
    """A student's submission for one assignment (one per student & assignment)."""

    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    student = models.ForeignKey(
        "schools.Student",
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Abgabe"
        verbose_name_plural = "Abgaben"
        ordering = ["student__number"]
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "student"],
                name="unique_submission_per_student",
            )
        ]

    def __str__(self):
        return f"Abgabe {self.student} – {self.assignment}"

    @property
    def is_late(self):
        due = self.assignment.due_date
        return bool(due and self.updated_at and self.updated_at > due)


class SubmissionFile(models.Model):
    """A file that belongs to a student's submission."""

    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name="files",
    )
    file = models.FileField(upload_to=submission_upload_path)
    original_name = models.CharField(max_length=255)
    size = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Abgabe-Datei"
        verbose_name_plural = "Abgabe-Dateien"
        ordering = ["uploaded_at"]

    def __str__(self):
        return self.original_name

    def save(self, *args, **kwargs):
        if self.file and not self.original_name:
            self.original_name = self.file.name.rsplit("/", 1)[-1]
        if self.file and not self.size:
            self.size = self.file.size
        super().save(*args, **kwargs)

    def get_download_url(self):
        return reverse("worksheets:submission_file_download", args=[self.pk])

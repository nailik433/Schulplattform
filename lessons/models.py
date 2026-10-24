import secrets

from django.conf import settings
from django.db import models
from django.urls import reverse


def generate_api_key():
    return "sk_" + secrets.token_urlsafe(32)


class Lesson(models.Model):
    """An interactive learning environment: a complete, self-contained HTML
    document (with its own CSS/JS/animations), authored by a teacher or by an
    AI via the API. Shown to students inside a sandboxed iframe."""

    school_class = models.ForeignKey(
        "schools.SchoolClass",
        on_delete=models.CASCADE,
        related_name="lessons",
    )
    title = models.CharField("Titel", max_length=200)
    html = models.TextField("HTML-Inhalt", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lessons_created",
    )
    # Set when this lesson was created from a project template.
    class_project = models.ForeignKey(
        "projects.ClassProject",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lessons",
    )
    project_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Lernumgebung"
        verbose_name_plural = "Lernumgebungen"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("lessons:lesson_detail", args=[self.pk])


class LessonResult(models.Model):
    """A student's result for a lesson. Written when the lesson's HTML reports
    a score back to the platform (via postMessage), or when it is opened."""

    lesson = models.ForeignKey(
        Lesson, on_delete=models.CASCADE, related_name="results"
    )
    student = models.ForeignKey(
        "schools.Student", on_delete=models.CASCADE, related_name="lesson_results"
    )
    score = models.FloatField(null=True, blank=True)
    max_score = models.FloatField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    detail = models.JSONField(default=dict, blank=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ergebnis (Lernumgebung)"
        verbose_name_plural = "Ergebnisse (Lernumgebungen)"
        ordering = ["student__number"]
        constraints = [
            models.UniqueConstraint(
                fields=["lesson", "student"], name="unique_result_per_student"
            )
        ]

    def __str__(self):
        return f"{self.student} – {self.lesson}"

    @property
    def percent(self):
        if not self.max_score:
            return None
        return round(100 * (self.score or 0) / self.max_score)


class ApiKey(models.Model):
    """Lets an external assistant (e.g. a Claude chat) create lessons in the
    teacher's classes through the HTTP API — without source-code access."""

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_keys",
    )
    key = models.CharField(
        max_length=80, unique=True, default=generate_api_key, editable=False
    )
    label = models.CharField(max_length=100, default="Standard")
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "API-Schlüssel"
        verbose_name_plural = "API-Schlüssel"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.label} ({self.teacher})"

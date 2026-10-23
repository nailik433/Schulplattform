import secrets

from django.conf import settings
from django.db import models
from django.urls import reverse


def generate_api_key():
    return "sk_" + secrets.token_urlsafe(32)


class Lesson(models.Model):
    """An interactive learning environment: an ordered list of content/question
    blocks stored as JSON (see lessons.grading for the schema)."""

    school_class = models.ForeignKey(
        "schools.SchoolClass",
        on_delete=models.CASCADE,
        related_name="lessons",
    )
    title = models.CharField("Titel", max_length=200)
    intro = models.TextField("Einleitung", blank=True)
    content = models.JSONField("Inhalt (Blöcke)", default=list)
    due_date = models.DateTimeField("Abgabe bis", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lessons_created",
    )
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

    @property
    def max_points(self):
        from .grading import content_max_points

        return content_max_points(self.content)

    @property
    def question_count(self):
        from .grading import GRADABLE_TYPES

        return sum(
            1 for b in self.content if isinstance(b, dict) and b.get("type") in GRADABLE_TYPES
        )


class LessonAttempt(models.Model):
    """A student's submission for a lesson (one per student & lesson; a new
    submission overwrites the previous)."""

    lesson = models.ForeignKey(
        Lesson, on_delete=models.CASCADE, related_name="attempts"
    )
    student = models.ForeignKey(
        "schools.Student", on_delete=models.CASCADE, related_name="lesson_attempts"
    )
    answers = models.JSONField(default=dict)
    results = models.JSONField(default=dict)
    score = models.FloatField(default=0)
    max_score = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Lösung (Lernumgebung)"
        verbose_name_plural = "Lösungen (Lernumgebungen)"
        ordering = ["student__number"]
        constraints = [
            models.UniqueConstraint(
                fields=["lesson", "student"], name="unique_attempt_per_student"
            )
        ]

    def __str__(self):
        return f"{self.student} – {self.lesson}"

    @property
    def percent(self):
        if not self.max_score:
            return 0
        return round(100 * self.score / self.max_score)


class ApiKey(models.Model):
    """An API key a teacher uses so an external assistant can create lessons
    in their classes via the HTTP API — without access to the source code."""

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_keys",
    )
    key = models.CharField(max_length=80, unique=True, default=generate_api_key, editable=False)
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

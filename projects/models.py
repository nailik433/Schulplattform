from django.conf import settings
from django.db import models
from django.urls import reverse


class Project(models.Model):
    """A reusable project template owned by one teacher.

    It bundles building blocks (learning environments, worksheets, tasks) and
    can be applied to any of the teacher's classes; applying it *copies* the
    blocks into the class, so later edits to the template never change what
    pupils already see."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    title = models.CharField("Titel", max_length=200)
    description = models.TextField("Beschreibung", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Projekt (Vorlage)"
        verbose_name_plural = "Projekte (Vorlagen)"
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("projects:detail", args=[self.pk])


class ProjectItem(models.Model):
    """One building block of a project template."""

    class Kind(models.TextChoices):
        LESSON = "lesson", "Lernumgebung"
        WORKSHEET = "worksheet", "Arbeitsblatt"
        TASK = "task", "Arbeitsauftrag (nur Abgabe)"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="items")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    position = models.PositiveIntegerField(default=0)
    title = models.CharField("Titel", max_length=200)
    description = models.TextField("Beschreibung / Aufgabe", blank=True)
    # Learning environment: the complete HTML page.
    html = models.TextField("HTML-Inhalt", blank=True)
    collect_submissions = models.BooleanField("Abgaben einsammeln", default=True)
    # Worksheet: files picked from the teacher's material library.
    material_files = models.ManyToManyField(
        "materials.MaterialFile", blank=True, related_name="project_items"
    )

    class Meta:
        verbose_name = "Projekt-Baustein"
        verbose_name_plural = "Projekt-Bausteine"
        ordering = ["position", "id"]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.title}"

    @property
    def icon(self):
        return {"lesson": "🧪", "worksheet": "📄", "task": "✍️"}.get(self.kind, "•")


class ClassProject(models.Model):
    """A project in a concrete class: the copied blocks (lessons and
    assignments of that class) point here, which lets pupils see them bundled
    on one card with a progress bar."""

    school_class = models.ForeignKey(
        "schools.SchoolClass", on_delete=models.CASCADE, related_name="projects"
    )
    project = models.ForeignKey(
        Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="class_projects"
    )
    title = models.CharField("Titel", max_length=200)
    description = models.TextField("Beschreibung", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="class_projects_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Projekt in Klasse"
        verbose_name_plural = "Projekte in Klassen"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.school_class})"

    def get_absolute_url(self):
        return reverse("projects:class_detail", args=[self.pk])

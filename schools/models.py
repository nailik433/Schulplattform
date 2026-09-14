import secrets

from django.conf import settings
from django.db import models
from django.urls import reverse

# Alphabet for student access codes. Deliberately excludes visually
# ambiguous characters (0/O, 1/I/L) so codes are easy to read aloud and
# type on a phone. All uppercase for the same reason.
ACCESS_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
ACCESS_CODE_LENGTH = 8


def generate_access_code(length=ACCESS_CODE_LENGTH):
    """Return a cryptographically random access code string."""
    return "".join(secrets.choice(ACCESS_CODE_ALPHABET) for _ in range(length))


class School(models.Model):
    """A school. Created by a teacher; classes live under it."""

    name = models.CharField("Name der Schule", max_length=200)
    # Set to the platform operator who created the school; kept for the record
    # only, so it may be empty (e.g. schools created via a data import).
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="schools_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Schule"
        verbose_name_plural = "Schulen"
        ordering = ["name"]

    def __str__(self):
        return self.name


class SchoolClass(models.Model):
    """A teaching group, e.g. "5a" in the subject "Informatik".

    Access is expressed through :class:`ClassMembership` rows rather than a
    single owner field. That makes it straightforward to later share a class
    with colleagues (a future stage) without changing this model.
    """

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="classes",
    )
    name = models.CharField("Klassenbezeichnung", max_length=100)
    subject = models.CharField("Fach", max_length=100, blank=True)
    teachers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="ClassMembership",
        related_name="classes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Klasse"
        verbose_name_plural = "Klassen"
        ordering = ["name"]

    def __str__(self):
        if self.subject:
            return f"{self.name} – {self.subject}"
        return self.name

    def get_absolute_url(self):
        return reverse("schools:class_detail", args=[self.pk])

    @property
    def owner(self):
        membership = self.memberships.filter(
            role=ClassMembership.Role.OWNER
        ).select_related("teacher").first()
        return membership.teacher if membership else None

    def active_student_count(self):
        return self.students.filter(is_active=True).count()


class ClassMembership(models.Model):
    """Links a teacher to a class with a role.

    The teacher who creates a class becomes its OWNER. COLLABORATOR is
    reserved for the "share with a colleague" feature in a later stage:
    collaborators may work with the class's students but never gain access
    to the owner's other classes.
    """

    class Role(models.TextChoices):
        OWNER = "owner", "Inhaber"
        COLLABORATOR = "collaborator", "Kollege/Kollegin"

    school_class = models.ForeignKey(
        SchoolClass,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="class_memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.OWNER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Klassen-Zugehörigkeit"
        verbose_name_plural = "Klassen-Zugehörigkeiten"
        constraints = [
            models.UniqueConstraint(
                fields=["school_class", "teacher"],
                name="unique_teacher_per_class",
            )
        ]

    def __str__(self):
        return f"{self.teacher} → {self.school_class} ({self.get_role_display()})"


class Student(models.Model):
    """A pupil, identified to the system only by a random access code.

    Students do not have email addresses or passwords: they log in with the
    access code alone, which keeps the amount of personal data minimal.
    """

    school_class = models.ForeignKey(
        SchoolClass,
        on_delete=models.CASCADE,
        related_name="students",
    )
    display_name = models.CharField("Anzeigename", max_length=150)
    access_code = models.CharField(max_length=16, unique=True, editable=False)
    is_active = models.BooleanField("aktiv", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Schüler/in"
        verbose_name_plural = "Schüler/innen"
        ordering = ["display_name"]

    def __str__(self):
        return self.display_name

    def save(self, *args, **kwargs):
        if not self.access_code:
            self.access_code = self._generate_unique_access_code()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_unique_access_code():
        # Loop until we hit a code not already in use. Collisions are
        # extremely unlikely with this alphabet/length, but we guarantee
        # uniqueness rather than rely on probability.
        for _ in range(100):
            code = generate_access_code()
            if not Student.objects.filter(access_code=code).exists():
                return code
        raise RuntimeError("Konnte keinen eindeutigen Zugangscode erzeugen.")

    def regenerate_access_code(self):
        self.access_code = self._generate_unique_access_code()
        self.save(update_fields=["access_code"])

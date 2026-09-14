import secrets
from datetime import timedelta

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


def generate_invitation_token():
    return secrets.token_urlsafe(32)


def default_invitation_expiry():
    return timezone.now() + timedelta(days=14)


class UserManager(BaseUserManager):
    """Manager for the email-based custom user model."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Es muss eine E-Mail-Adresse angegeben werden.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser muss is_staff=True haben.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser muss is_superuser=True haben.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """A teacher account. Log in happens with the email address."""

    # Drop the username field; email is the unique identifier.
    username = None
    email = models.EmailField("E-Mail-Adresse", unique=True)

    # The school a teacher belongs to. Set when they accept an invitation.
    # Platform operators (superusers) have no school.
    school = models.ForeignKey(
        "schools.School",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teachers",
        verbose_name="Schule",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = "Lehrkraft"
        verbose_name_plural = "Lehrkräfte"

    def __str__(self):
        full_name = self.get_full_name()
        return full_name or self.email


class TeacherInvitation(models.Model):
    """A one-time invitation that lets a teacher create an account for a
    specific school. Created by the platform operator directly, or generated
    automatically when an access request is approved."""

    email = models.EmailField("E-Mail-Adresse")
    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        related_name="invitations",
        verbose_name="Schule",
    )
    first_name = models.CharField("Vorname", max_length=150, blank=True)
    last_name = models.CharField("Nachname", max_length=150, blank=True)
    token = models.CharField(
        max_length=64, unique=True, default=generate_invitation_token, editable=False
    )
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_invitations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=default_invitation_expiry)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Einladung"
        verbose_name_plural = "Einladungen"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Einladung für {self.email} ({self.school})"

    @property
    def is_accepted(self):
        return self.accepted_at is not None

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return not self.is_accepted and not self.is_expired


class TeacherAccessRequest(models.Model):
    """A teacher's request to join a school. The operator approves or rejects
    it; approval creates a TeacherInvitation."""

    class Status(models.TextChoices):
        PENDING = "pending", "Offen"
        APPROVED = "approved", "Genehmigt"
        REJECTED = "rejected", "Abgelehnt"

    first_name = models.CharField("Vorname", max_length=150)
    last_name = models.CharField("Nachname", max_length=150)
    email = models.EmailField("E-Mail-Adresse")
    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        related_name="access_requests",
        verbose_name="Schule",
    )
    message = models.TextField("Nachricht", blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    invitation = models.ForeignKey(
        TeacherInvitation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="access_requests",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Zugangsanfrage"
        verbose_name_plural = "Zugangsanfragen"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} → {self.school} ({self.get_status_display()})"

"""Helpers for the invitation flow (URL building and email sending)."""

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse


def build_invitation_url(invitation, request=None):
    """Return an absolute URL for accepting the given invitation.

    Uses the current request when available (e.g. from the admin), otherwise
    falls back to the DJANGO_SITE_URL setting so the link is still usable in
    background contexts.
    """
    path = reverse("accounts:invitation_accept", args=[invitation.token])
    if request is not None:
        return request.build_absolute_uri(path)
    base = getattr(settings, "SITE_URL", "").rstrip("/")
    return f"{base}{path}" if base else path


def send_invitation_email(invitation, url):
    """Send the invitation link by email. Best-effort: with the default
    console backend this simply prints the message to the server log."""
    subject = "Einladung zur Schulplattform"
    school = invitation.school.name
    body = (
        f"Hallo,\n\n"
        f"du wurdest eingeladen, ein Lehrer-Konto für die Schule „{school}“ "
        f"auf der Schulplattform anzulegen.\n\n"
        f"Öffne dazu diesen Link und setze dein Passwort:\n{url}\n\n"
        f"Der Link ist bis zum {invitation.expires_at:%d.%m.%Y} gültig.\n"
    )
    send_mail(
        subject,
        body,
        getattr(settings, "DEFAULT_FROM_EMAIL", None),
        [invitation.email],
        fail_silently=True,
    )

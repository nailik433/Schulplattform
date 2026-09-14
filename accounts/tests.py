from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from schools.models import School

from .models import TeacherAccessRequest, TeacherInvitation

User = get_user_model()


class AccessRequestTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Testschule")

    def test_request_creates_pending_entry(self):
        response = self.client.post(
            reverse("accounts:access_request"),
            {
                "first_name": "Anna",
                "last_name": "Beispiel",
                "email": "Anna@Example.com",
                "school": self.school.pk,
                "message": "Informatik",
            },
        )
        self.assertEqual(response.status_code, 200)
        req = TeacherAccessRequest.objects.get()
        self.assertEqual(req.email, "anna@example.com")  # normalised
        self.assertEqual(req.status, TeacherAccessRequest.Status.PENDING)

    def test_request_rejected_for_existing_user(self):
        User.objects.create_user(email="da@example.com", password="pw-really-strong-1")
        response = self.client.post(
            reverse("accounts:access_request"),
            {
                "first_name": "D",
                "last_name": "A",
                "email": "da@example.com",
                "school": self.school.pk,
            },
        )
        self.assertContains(response, "bereits ein Konto")
        self.assertFalse(TeacherAccessRequest.objects.exists())


class InvitationTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Testschule")

    def _invite(self, email="neu@example.com", **kwargs):
        return TeacherInvitation.objects.create(
            email=email, school=self.school, **kwargs
        )

    def test_accept_creates_account_with_school(self):
        invitation = self._invite()
        response = self.client.post(
            reverse("accounts:invitation_accept", args=[invitation.token]),
            {
                "first_name": "Neu",
                "last_name": "Lehrer",
                "password1": "einSicheres!PW9",
                "password2": "einSicheres!PW9",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(email="neu@example.com")
        self.assertEqual(user.school, self.school)
        self.assertTrue(user.check_password("einSicheres!PW9"))
        invitation.refresh_from_db()
        self.assertTrue(invitation.is_accepted)
        self.assertTrue(response.context["user"].is_authenticated)

    def test_invitation_cannot_be_used_twice(self):
        invitation = self._invite(accepted_at=timezone.now())
        response = self.client.get(
            reverse("accounts:invitation_accept", args=[invitation.token])
        )
        self.assertEqual(response.status_code, 410)

    def test_unknown_token_is_404(self):
        response = self.client.get(
            reverse("accounts:invitation_accept", args=["does-not-exist"])
        )
        self.assertEqual(response.status_code, 404)

    def test_approving_request_creates_invitation(self):
        req = TeacherAccessRequest.objects.create(
            first_name="Carla",
            last_name="Kollegin",
            email="carla@example.com",
            school=self.school,
        )
        admin = User.objects.create_superuser(
            email="admin@example.com", password="admin-pw-strong-9"
        )
        self.client.force_login(admin)
        # Trigger the admin action.
        self.client.post(
            reverse("admin:accounts_teacheraccessrequest_changelist"),
            {
                "action": "approve_requests",
                "_selected_action": [req.pk],
            },
        )
        req.refresh_from_db()
        self.assertEqual(req.status, TeacherAccessRequest.Status.APPROVED)
        self.assertIsNotNone(req.invitation)
        self.assertEqual(req.invitation.email, "carla@example.com")
        self.assertEqual(req.invitation.school, self.school)


class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="reset@example.com", password="altes-PW-9xyz", first_name="R", last_name="U"
        )

    def test_reset_sends_email_for_known_address(self):
        from django.core import mail

        response = self.client.post(
            reverse("accounts:password_reset"), {"email": "reset@example.com"}
        )
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("passwort/neu/", mail.outbox[0].body)

    def test_no_email_for_unknown_address(self):
        from django.core import mail

        self.client.post(
            reverse("accounts:password_reset"), {"email": "unbekannt@example.com"}
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_full_reset_flow_sets_new_password(self):
        from django.core import mail
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        self.client.post(
            reverse("accounts:password_reset"), {"email": "reset@example.com"}
        )
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        # GET first (the view moves the token into the session), then POST.
        confirm_url = reverse(
            "accounts:password_reset_confirm", kwargs={"uidb64": uid, "token": token}
        )
        self.client.get(confirm_url)
        response = self.client.post(
            confirm_url.replace(token, "set-password"),
            {"new_password1": "ganzNeues-PW-42", "new_password2": "ganzNeues-PW-42"},
        )
        self.assertRedirects(response, reverse("accounts:password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ganzNeues-PW-42"))


class UserModelTests(TestCase):
    def test_email_is_normalised_and_login_case_insensitive(self):
        User.objects.create_user(email="Mix@Example.com", password="pw-strong-xyz-1")
        # EmailBackend matches case-insensitively.
        ok = self.client.login(username="mix@example.com", password="pw-strong-xyz-1")
        self.assertTrue(ok)

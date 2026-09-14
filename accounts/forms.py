from django import forms
from django.contrib.auth import get_user_model, password_validation

from .models import TeacherAccessRequest

User = get_user_model()


class AccessRequestForm(forms.ModelForm):
    """Form a prospective teacher fills in to request access to a school."""

    class Meta:
        model = TeacherAccessRequest
        fields = ["first_name", "last_name", "email", "school", "message"]
        widgets = {
            "message": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "z. B. Fach/Rolle, damit die Schule dich zuordnen kann",
                }
            ),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Mit dieser E-Mail-Adresse besteht bereits ein Konto. "
                "Melde dich stattdessen an."
            )
        return email


class InvitationAcceptForm(forms.Form):
    """Set name and password when accepting an invitation. Email and school
    come from the invitation itself, not from user input."""

    first_name = forms.CharField(label="Vorname", max_length=150)
    last_name = forms.CharField(label="Nachname", max_length=150)
    password1 = forms.CharField(
        label="Passwort", strip=False, widget=forms.PasswordInput
    )
    password2 = forms.CharField(
        label="Passwort bestätigen", strip=False, widget=forms.PasswordInput
    )

    def __init__(self, *args, invitation=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.invitation = invitation
        if invitation:
            self.fields["first_name"].initial = invitation.first_name
            self.fields["last_name"].initial = invitation.last_name

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Die Passwörter stimmen nicht überein.")
        password_validation.validate_password(p2)
        return p2

    def save(self):
        invitation = self.invitation
        user = User.objects.create_user(
            email=invitation.email,
            password=self.cleaned_data["password1"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            school=invitation.school,
        )
        return user

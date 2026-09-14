from django import forms

from .models import SchoolClass, Student


class SchoolClassForm(forms.ModelForm):
    class Meta:
        model = SchoolClass
        fields = ["name", "subject"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "z. B. 5a"}),
            "subject": forms.TextInput(attrs={"placeholder": "z. B. Informatik"}),
        }


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ["display_name"]
        widgets = {
            "display_name": forms.TextInput(
                attrs={"placeholder": "optional, z. B. Max M. (leer = nur Nummer)"}
            ),
        }


class CountStudentForm(forms.Form):
    """Create a number of anonymous, numbered students at once (like VokaGo:
    a class with X students, each identified only by number + token)."""

    count = forms.IntegerField(
        label="Anzahl Schüler/innen",
        min_value=1,
        max_value=60,
        widget=forms.NumberInput(attrs={"placeholder": "z. B. 28"}),
        help_text="Es werden anonyme Plätze (#001, #002 …) mit je einem Token erzeugt.",
    )


class BulkStudentForm(forms.Form):
    """Add several students at once by name, one per line."""

    names = forms.CharField(
        label="Namen (eine/r pro Zeile)",
        widget=forms.Textarea(attrs={"rows": 6, "placeholder": "Anna B.\nBen C.\nClara D."}),
        help_text="Für jede Zeile wird ein Token erzeugt.",
    )

    def clean_names(self):
        raw = self.cleaned_data["names"]
        names = [line.strip() for line in raw.splitlines() if line.strip()]
        if not names:
            raise forms.ValidationError("Bitte mindestens einen Namen eingeben.")
        return names


class StudentLoginForm(forms.Form):
    access_code = forms.CharField(
        label="Zugangscode",
        max_length=16,
        widget=forms.TextInput(
            attrs={
                "placeholder": "z. B. hgk9ezgy3s8x",
                "autocapitalize": "none",
                "autocomplete": "off",
                "spellcheck": "false",
                "autofocus": "autofocus",
            }
        ),
    )

    def clean_access_code(self):
        # Tokens are lowercase without spaces; normalise input so pupils can
        # type upper case or add stray spaces.
        return self.cleaned_data["access_code"].strip().lower().replace(" ", "")

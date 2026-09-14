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
                attrs={"placeholder": "z. B. Max M. oder Sitzplatz 12"}
            ),
        }


class BulkStudentForm(forms.Form):
    """Add several students at once, one name per line."""

    names = forms.CharField(
        label="Namen (eine/r pro Zeile)",
        widget=forms.Textarea(attrs={"rows": 6, "placeholder": "Anna B.\nBen C.\nClara D."}),
        help_text="Für jede Zeile wird ein Zugangscode erzeugt.",
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
                "placeholder": "z. B. K7QMB4RT",
                "autocapitalize": "characters",
                "autocomplete": "off",
                "autofocus": "autofocus",
            }
        ),
    )

    def clean_access_code(self):
        # Codes are stored uppercase without spaces; normalise input so
        # pupils can type lower case or add stray spaces.
        return self.cleaned_data["access_code"].strip().upper().replace(" ", "")

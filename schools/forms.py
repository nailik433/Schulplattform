import re

from django import forms

from .models import SchoolClass, Student

# A valid student token: 3–16 lowercase letters/digits.
TOKEN_RE = re.compile(r"^[a-z0-9]{3,16}$")


def normalize_token(raw):
    return str(raw).strip().lower().replace(" ", "")


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


class ClassDeleteConfirmForm(forms.Form):
    """Require the user to type the word "löschen" to confirm deletion."""

    confirm = forms.CharField(
        label='Zum Bestätigen „löschen" eingeben',
        widget=forms.TextInput(attrs={"placeholder": "löschen", "autocomplete": "off"}),
    )

    def clean_confirm(self):
        value = self.cleaned_data["confirm"].strip().lower()
        if value != "löschen":
            raise forms.ValidationError('Bitte genau das Wort „löschen" eingeben.')
        return value


class StudentImportForm(forms.Form):
    """Import students with existing tokens, e.g. pasted from two Excel columns
    (Bezeichnung + Token)."""

    data = forms.CharField(
        label="Liste einfügen",
        widget=forms.Textarea(
            attrs={
                "rows": 8,
                "placeholder": "7b-001\ta1b2c3\n7b-002\td4e5f6\n…  (oder nur die Token-Spalte)",
            }
        ),
        help_text="Eine Zeile pro Schüler/in. Zwei Spalten (Tab/Komma/Semikolon): "
        "erste = Bezeichnung (optional), zweite = Token. Eine Spalte = nur Token.",
    )

    def clean_data(self):
        lines = [l for l in self.cleaned_data["data"].splitlines() if l.strip()]
        if not lines:
            raise forms.ValidationError("Bitte mindestens eine Zeile einfügen.")
        entries, seen, errors = [], set(), []
        for n, line in enumerate(lines, 1):
            parts = [p.strip() for p in re.split(r"[\t;,]", line) if p.strip()]
            if not parts:
                continue
            if len(parts) == 1:
                label, raw_token = "", parts[0]
            else:
                label, raw_token = parts[0], parts[-1]
            token = normalize_token(raw_token)
            if not TOKEN_RE.match(token):
                errors.append(
                    f"Zeile {n}: Token „{raw_token}“ ungültig (3–16 Kleinbuchstaben/Ziffern)."
                )
                continue
            if token in seen:
                errors.append(f"Zeile {n}: Token „{token}“ kommt doppelt vor.")
                continue
            seen.add(token)
            entries.append((label[:150], token))
        if errors:
            raise forms.ValidationError(errors)
        return entries


class SetTokenForm(forms.Form):
    token = forms.CharField(max_length=16)

    def clean_token(self):
        token = normalize_token(self.cleaned_data["token"])
        if not TOKEN_RE.match(token):
            raise forms.ValidationError(
                "Token muss 3–16 Kleinbuchstaben/Ziffern sein."
            )
        return token


class ShareClassForm(forms.Form):
    """Share a class with a colleague, identified by their email address."""

    email = forms.EmailField(
        label="E-Mail der Kollegin / des Kollegen",
        widget=forms.EmailInput(attrs={"placeholder": "kolleg.in@schule.de"}),
    )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class StudentLoginForm(forms.Form):
    access_code = forms.CharField(
        label="Zugangscode",
        max_length=16,
        widget=forms.TextInput(
            attrs={
                "placeholder": "z. B. k7m3np",
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

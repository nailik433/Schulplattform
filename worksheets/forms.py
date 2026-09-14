from django import forms

from .models import MAX_UPLOAD_SIZE, Assignment


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """A file field that accepts several files at once (the Django-recommended
    pattern for multiple uploads)."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            files = [single_clean(item, initial) for item in data]
        else:
            files = [single_clean(data, initial)]
        for f in files:
            if f and f.size > MAX_UPLOAD_SIZE:
                raise forms.ValidationError(
                    f"„{f.name}“ ist zu groß (max. "
                    f"{MAX_UPLOAD_SIZE // (1024 * 1024)} MB pro Datei)."
                )
        return files


class AssignmentForm(forms.ModelForm):
    files = MultipleFileField(
        label="Dateien (Arbeitsblätter)",
        required=False,
        help_text="Ein oder mehrere Dateien, z. B. PDFs. Optional.",
    )

    class Meta:
        model = Assignment
        fields = ["title", "description", "due_date", "collect_submissions"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "z. B. Arbeitsblatt 3 – Schleifen"}),
            "description": forms.Textarea(attrs={"rows": 4}),
            "due_date": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Let the browser's datetime-local control populate an existing value.
        self.fields["due_date"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"]


class SubmissionForm(forms.Form):
    """A student uploads one or more solution files."""

    files = MultipleFileField(label="Deine Datei(en)", required=True)

from datetime import timedelta

from django import forms
from django.forms.utils import to_current_timezone

from materials.models import MaterialFile

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


# --------------------------------------------------------------------------
# Deadline in half-hour steps
# --------------------------------------------------------------------------

HALF_HOUR_CHOICES = [
    (f"{h:02d}:{m:02d}", f"{h:02d}:{m:02d} Uhr") for h in range(24) for m in (0, 30)
]
DEFAULT_DUE_TIME = "08:00"


def round_to_half_hour(value):
    """Round a naive datetime to the nearest half hour (ties go up)."""
    minutes = (value.hour * 60 + value.minute + 15) // 30 * 30
    midnight = value.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight + timedelta(minutes=minutes)


class HalfHourDateTimeWidget(forms.MultiWidget):
    """A date picker plus a time drop-down with 30-minute steps.

    A drop-down behaves the same on every device. ``<input type="datetime-local" step=1800>``
    is ignored by iPadOS/iOS, where the picker would still offer every minute.
    """

    def __init__(self, attrs=None):
        widgets = [
            forms.DateInput(attrs={"type": "date", "class": "dt-date"}, format="%Y-%m-%d"),
            forms.Select(
                attrs={"class": "dt-time", "aria-label": "Uhrzeit"},
                choices=HALF_HOUR_CHOICES,
            ),
        ]
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if not value:
            return [None, DEFAULT_DUE_TIME]
        # Deadlines saved before this change may have odd minutes: show them
        # rounded so the drop-down always has a matching entry.
        local = round_to_half_hour(to_current_timezone(value))
        return [local.date(), local.strftime("%H:%M")]


class HalfHourDateTimeField(forms.SplitDateTimeField):
    widget = HalfHourDateTimeWidget

    def __init__(self, **kwargs):
        kwargs.setdefault("input_time_formats", ["%H:%M"])
        super().__init__(**kwargs)

    def compress(self, data_list):
        # No date means "no deadline", whatever the time drop-down says.
        if not data_list or data_list[0] in self.empty_values:
            return None
        if data_list[1] is not None and data_list[1].minute % 30:
            raise forms.ValidationError(
                "Bitte eine volle oder halbe Stunde wählen.", code="half_hour"
            )
        return super().compress(data_list)


class AssignmentForm(forms.ModelForm):
    files = MultipleFileField(
        label="Dateien (Arbeitsblätter)",
        required=False,
        help_text="Ein oder mehrere Dateien, z. B. PDFs. Optional.",
    )
    due_date = HalfHourDateTimeField(
        label="Abgabe bis",
        required=False,
        help_text="Optional. Ohne Datum gibt es keine Frist. Die Uhrzeit gilt in 30-Minuten-Schritten.",
    )
    material_files = forms.ModelMultipleChoiceField(
        queryset=MaterialFile.objects.none(),
        required=False,
        label="Aus „Mein Material“",
    )

    class Meta:
        model = Assignment
        fields = ["title", "description", "due_date", "collect_submissions"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "z. B. Arbeitsblatt 3 – Schleifen"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["material_files"].queryset = MaterialFile.objects.filter(owner=user)


class SubmissionForm(forms.Form):
    """A student uploads one or more solution files."""

    files = MultipleFileField(label="Deine Datei(en)", required=True)

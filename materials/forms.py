from django import forms

from worksheets.forms import MultipleFileField

from .models import MaterialFolder


class FolderNameForm(forms.Form):
    """A valid, unique (among siblings) folder name."""

    name = forms.CharField(max_length=120)

    def __init__(self, *args, owner, parent=None, exclude_pk=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner, self.parent, self.exclude_pk = owner, parent, exclude_pk

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        if not name:
            raise forms.ValidationError("Bitte einen Namen eingeben.")
        if "/" in name or "\\" in name:
            raise forms.ValidationError("Der Name darf kein / oder \\ enthalten.")
        siblings = MaterialFolder.objects.filter(owner=self.owner, parent=self.parent)
        if self.exclude_pk:
            siblings = siblings.exclude(pk=self.exclude_pk)
        if siblings.filter(name__iexact=name).exists():
            raise forms.ValidationError(f"Hier gibt es schon einen Ordner „{name}“.")
        return name


class FileNameForm(forms.Form):
    name = forms.CharField(max_length=255)

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        if not name:
            raise forms.ValidationError("Bitte einen Namen eingeben.")
        if "/" in name or "\\" in name:
            raise forms.ValidationError("Der Name darf kein / oder \\ enthalten.")
        return name


class UploadForm(forms.Form):
    files = MultipleFileField(label="Dateien", required=True)

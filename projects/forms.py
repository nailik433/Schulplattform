from django import forms

from lessons.models import Lesson
from materials.models import MaterialFile
from schools.models import SchoolClass
from worksheets.forms import HalfHourDateTimeField

from .models import Project, ProjectItem


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["title", "description"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "z. B. Bit, Byte und Buchstaben"}),
            "description": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Worum geht es? (Schüler/innen sehen das auf der Projektkarte.)"}
            ),
        }


class _LessonChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.school_class.name} · {obj.title}"


class ProjectItemForm(forms.ModelForm):
    """One building block. Which fields matter depends on ``kind``:
    a learning environment needs HTML, a worksheet needs files from the
    material library, a task (\"Arbeitsauftrag\") only asks for a submission."""

    copy_from_lesson = _LessonChoice(
        queryset=Lesson.objects.none(),
        required=False,
        label="… oder eine bestehende Lernumgebung übernehmen",
        empty_label="– nicht übernehmen –",
    )
    material_files = forms.ModelMultipleChoiceField(
        queryset=MaterialFile.objects.none(), required=False
    )

    class Meta:
        model = ProjectItem
        fields = ["title", "description", "html", "collect_submissions"]
        widgets = {
            "title": forms.TextInput(),
            "description": forms.Textarea(attrs={"rows": 4}),
            "html": forms.Textarea(
                attrs={
                    "rows": 14,
                    "spellcheck": "false",
                    "placeholder": "Die komplette HTML-Seite hier einfügen (z. B. von Claude erzeugt) …",
                    "style": "font-family:ui-monospace,Menlo,Consolas,monospace;",
                }
            ),
        }

    def __init__(self, *args, kind, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.kind = kind
        self.fields["material_files"].queryset = MaterialFile.objects.filter(owner=owner)
        self.fields["copy_from_lesson"].queryset = (
            Lesson.objects.filter(school_class__memberships__teacher=owner)
            .select_related("school_class")
            .distinct()
        )
        self.fields["title"].label = "Titel"
        placeholders = {
            ProjectItem.Kind.LESSON: "z. B. Bit-Labor",
            ProjectItem.Kind.WORKSHEET: "z. B. Arbeitsblatt 1 – Zahlensysteme",
            ProjectItem.Kind.TASK: "z. B. Erstelle eine Präsentation",
        }
        self.fields["title"].widget.attrs["placeholder"] = placeholders[kind]
        self.fields["html"].required = False
        self.fields["description"].required = False

    def clean(self):
        cleaned = super().clean()
        K = ProjectItem.Kind
        if self.kind == K.LESSON:
            source = cleaned.get("copy_from_lesson")
            if not (cleaned.get("html") or "").strip():
                if source and source.html.strip():
                    cleaned["html"] = source.html
                else:
                    self.add_error("html", "Bitte HTML einfügen oder eine bestehende Lernumgebung übernehmen.")
        elif self.kind == K.WORKSHEET:
            if not cleaned.get("material_files"):
                self.add_error(
                    "material_files",
                    "Bitte mindestens eine Datei aus „Mein Material“ auswählen. "
                    "(Ohne Datei: Baustein „Arbeitsauftrag“ nehmen.)",
                )
        elif self.kind == K.TASK:
            if not (cleaned.get("description") or "").strip():
                self.add_error("description", "Bitte beschreiben, was die Schüler/innen abgeben sollen.")
        return cleaned

    def save(self, commit=True):
        item = super().save(commit=False)
        K = ProjectItem.Kind
        item.kind = self.kind
        if self.kind != K.LESSON:
            item.html = ""
        else:
            item.html = self.cleaned_data.get("html", item.html)
        if self.kind == K.TASK:
            item.collect_submissions = True
        if commit:
            item.save()
            item.material_files.set(
                self.cleaned_data["material_files"] if self.kind == K.WORKSHEET else []
            )
        return item


class ApplyToClassesForm(forms.Form):
    classes = forms.ModelMultipleChoiceField(
        queryset=SchoolClass.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label="In welche Klassen?",
        error_messages={"required": "Bitte mindestens eine Klasse auswählen."},
    )
    due_date = HalfHourDateTimeField(
        label="Abgabe bis",
        required=False,
        help_text="Optional. Gilt für alle Bausteine, bei denen Abgaben eingesammelt werden. "
        "Du kannst es später je Arbeitsblatt ändern.",
    )

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["classes"].queryset = SchoolClass.objects.filter(
            memberships__teacher=owner
        ).distinct().order_by("name")


class ApplyProjectForm(forms.Form):
    project = forms.ModelChoiceField(
        queryset=Project.objects.none(),
        widget=forms.RadioSelect,
        label="Welches Projekt?",
        empty_label=None,
        error_messages={"required": "Bitte ein Projekt auswählen."},
    )
    due_date = HalfHourDateTimeField(
        label="Abgabe bis",
        required=False,
        help_text="Optional. Gilt für alle Bausteine, bei denen Abgaben eingesammelt werden.",
    )

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = Project.objects.filter(owner=owner)

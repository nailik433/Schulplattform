from django import forms

from .models import Lesson


class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ["title", "html"]
        widgets = {
            "title": forms.TextInput(
                attrs={"placeholder": "z. B. Magnetismus – Klasse 7"}
            ),
            "html": forms.Textarea(
                attrs={
                    "rows": 16,
                    "placeholder": "Die komplette HTML-Seite hier einfügen "
                    "(von Claude erzeugt) …",
                    "spellcheck": "false",
                    "style": "font-family:ui-monospace,Menlo,Consolas,monospace;",
                }
            ),
        }

import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse


def material_upload_path(instance, filename):
    """Store material under an unguessable path per teacher. Downloads always
    go through the access-checked view, never through a public URL."""
    return f"material/user_{instance.owner_id}/{uuid.uuid4().hex}/{filename}"


class MaterialFolder(models.Model):
    """A folder in a teacher's private material library (may be nested)."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="material_folders",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    name = models.CharField("Name", max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Material-Ordner"
        verbose_name_plural = "Material-Ordner"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("materials:folder", args=[self.pk])


class MaterialFile(models.Model):
    """A file in a teacher's private material library."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="material_files",
    )
    folder = models.ForeignKey(
        MaterialFolder,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="files",
    )
    file = models.FileField(upload_to=material_upload_path)
    original_name = models.CharField(max_length=255)
    size = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Material-Datei"
        verbose_name_plural = "Material-Dateien"
        ordering = ["original_name"]

    def __str__(self):
        return self.original_name

    def save(self, *args, **kwargs):
        if self.file and not self.original_name:
            self.original_name = self.file.name.rsplit("/", 1)[-1]
        if self.file and not self.size:
            self.size = self.file.size
        super().save(*args, **kwargs)

    def get_download_url(self):
        return reverse("materials:file_download", args=[self.pk])

from django.urls import path

from . import views

app_name = "worksheets"

urlpatterns = [
    path(
        "klasse/<int:class_pk>/arbeitsblatt/neu/",
        views.assignment_create,
        name="assignment_create",
    ),
    path("arbeitsblatt/<int:pk>/", views.assignment_detail, name="assignment_detail"),
    path(
        "arbeitsblatt/<int:pk>/bearbeiten/",
        views.assignment_edit,
        name="assignment_edit",
    ),
    path(
        "arbeitsblatt/<int:pk>/loeschen/",
        views.assignment_delete,
        name="assignment_delete",
    ),
    path("datei/<int:file_pk>/", views.file_download, name="file_download"),
    path("datei/<int:file_pk>/loeschen/", views.file_delete, name="file_delete"),
]

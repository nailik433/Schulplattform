from django.urls import path

from . import views

app_name = "materials"

urlpatterns = [
    path("material/", views.browse, name="home"),
    path("material/ordner/<int:folder_pk>/", views.browse, name="folder"),
    path("material/ordner-anlegen/", views.folder_create, name="folder_create"),
    path("material/hochladen/", views.upload, name="upload"),
    path("material/ordner/<int:pk>/umbenennen/", views.folder_rename, name="folder_rename"),
    path("material/ordner/<int:pk>/verschieben/", views.folder_move, name="folder_move"),
    path("material/ordner/<int:pk>/loeschen/", views.folder_delete, name="folder_delete"),
    path("material/datei/<int:pk>/", views.file_download, name="file_download"),
    path("material/datei/<int:pk>/umbenennen/", views.file_rename, name="file_rename"),
    path("material/datei/<int:pk>/verschieben/", views.file_move, name="file_move"),
    path("material/datei/<int:pk>/loeschen/", views.file_delete, name="file_delete"),
]

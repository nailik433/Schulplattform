from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("projekte/", views.project_list, name="list"),
    path("projekte/neu/", views.project_create, name="create"),
    path("projekte/<int:pk>/", views.project_detail, name="detail"),
    path("projekte/<int:pk>/bearbeiten/", views.project_edit, name="edit"),
    path("projekte/<int:pk>/loeschen/", views.project_delete, name="delete"),
    path("projekte/<int:pk>/einsetzen/", views.project_apply, name="apply"),
    path("projekte/<int:pk>/baustein/neu/<str:kind>/", views.item_create, name="item_create"),
    path("projekte/baustein/<int:pk>/bearbeiten/", views.item_edit, name="item_edit"),
    path("projekte/baustein/<int:pk>/loeschen/", views.item_delete, name="item_delete"),
    path("projekte/baustein/<int:pk>/<str:direction>/", views.item_move, name="item_move"),
    path("klasse/<int:class_pk>/projekt-einsetzen/", views.class_apply, name="class_apply"),
    path("klassenprojekt/<int:pk>/", views.class_project_detail, name="class_detail"),
    path("klassenprojekt/<int:pk>/aufloesen/", views.class_project_detach, name="class_detach"),
    path("klassenprojekt/<int:pk>/loeschen/", views.class_project_delete, name="class_delete"),
]

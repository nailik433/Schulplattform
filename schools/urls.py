from django.urls import path

from . import views

app_name = "schools"

urlpatterns = [
    # Teacher area
    path("uebersicht/", views.dashboard, name="dashboard"),
    path("klasse/neu/", views.class_create, name="class_create"),
    path("klasse/<int:pk>/", views.class_detail, name="class_detail"),
    path("klasse/<int:pk>/qr/", views.class_qr_document, name="class_qr_document"),
    path("klasse/<int:pk>/schueler/hinzufuegen/", views.student_add, name="student_add"),
    path(
        "klasse/<int:pk>/schueler/anzahl/",
        views.student_add_count,
        name="student_add_count",
    ),
    path(
        "klasse/<int:pk>/schueler/mehrere/",
        views.student_bulk_add,
        name="student_bulk_add",
    ),
    path(
        "klasse/<int:pk>/schueler/<int:student_pk>/code-neu/",
        views.student_regenerate_code,
        name="student_regenerate_code",
    ),
    path(
        "klasse/<int:pk>/schueler/<int:student_pk>/aktiv/",
        views.student_toggle_active,
        name="student_toggle_active",
    ),
    path(
        "klasse/<int:pk>/schueler/<int:student_pk>/loeschen/",
        views.student_delete,
        name="student_delete",
    ),
    # Student area. Literal routes first, then the token catch-all.
    path("s/", views.student_login, name="student_login"),
    path("s/abmelden/", views.student_logout, name="student_logout"),
    path("s/<str:token>/", views.student_space, name="student_space"),
]

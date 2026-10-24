from django.urls import path

from . import api, mcp, views

app_name = "lessons"

urlpatterns = [
    # Teacher
    path("klasse/<int:class_pk>/lernumgebung/neu/", views.lesson_create, name="lesson_create"),
    path("lernumgebung/<int:pk>/", views.lesson_detail, name="lesson_detail"),
    path("lernumgebung/<int:pk>/bearbeiten/", views.lesson_edit, name="lesson_edit"),
    path("lernumgebung/<int:pk>/vorschau/", views.lesson_preview, name="lesson_preview"),
    path("lernumgebung/<int:pk>/schueler/<int:student_pk>/", views.result_detail, name="result_detail"),
    path("lernumgebung/<int:pk>/loeschen/", views.lesson_delete, name="lesson_delete"),
    path(
        "lernumgebung/<int:pk>/zwischenstand/zuruecksetzen/",
        views.state_reset_all,
        name="state_reset_all",
    ),
    path(
        "lernumgebung/<int:pk>/zwischenstand/<int:student_pk>/zuruecksetzen/",
        views.state_reset,
        name="state_reset",
    ),
    path("konto/api-schluessel/", views.api_key_page, name="api_key"),
    # Student
    path("l/<int:pk>/", views.lesson_play, name="lesson_play"),
    path("l/<int:pk>/inhalt/", views.lesson_content, name="lesson_content"),
    path("l/<int:pk>/ergebnis/", views.lesson_report, name="lesson_report"),
    path("l/<int:pk>/zwischenstand/", views.lesson_state_save, name="lesson_state"),
    # API (KI-Schnittstelle)
    path("api/classes", api.api_classes, name="api_classes"),
    path("api/lessons", api.api_lessons, name="api_lessons"),
    # Remote MCP server (Cowork / claude.ai custom connector)
    path("mcp", mcp.mcp_endpoint, name="mcp"),
    path("mcp/", mcp.mcp_endpoint),
    path("mcp/<str:key>/", mcp.mcp_endpoint, name="mcp_keyed"),
    path("mcp/<str:key>", mcp.mcp_endpoint),
]

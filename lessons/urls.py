from django.urls import path

from . import api, mcp, views

app_name = "lessons"

urlpatterns = [
    # Teacher
    path("klasse/<int:class_pk>/lernumgebung/neu/", views.lesson_create, name="lesson_create"),
    path("lernumgebung/<int:pk>/", views.lesson_detail, name="lesson_detail"),
    path("lernumgebung/<int:pk>/bearbeiten/", views.lesson_edit, name="lesson_edit"),
    path("lernumgebung/<int:pk>/vorschau/", views.lesson_preview, name="lesson_preview"),
    path("lernumgebung/<int:pk>/loeschen/", views.lesson_delete, name="lesson_delete"),
    path("konto/api-schluessel/", views.api_key_page, name="api_key"),
    # Student
    path("l/<int:pk>/", views.lesson_play, name="lesson_play"),
    path("l/<int:pk>/inhalt/", views.lesson_content, name="lesson_content"),
    path("l/<int:pk>/ergebnis/", views.lesson_report, name="lesson_report"),
    # API (KI-Schnittstelle)
    path("api/classes", api.api_classes, name="api_classes"),
    path("api/lessons", api.api_lessons, name="api_lessons"),
    # Remote MCP server (Cowork / claude.ai custom connector)
    path("mcp", mcp.mcp_endpoint, name="mcp"),
    path("mcp/", mcp.mcp_endpoint),
    path("mcp/<str:key>/", mcp.mcp_endpoint, name="mcp_keyed"),
    path("mcp/<str:key>", mcp.mcp_endpoint),
]

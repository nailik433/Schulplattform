from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("anmelden/", views.TeacherLoginView.as_view(), name="login"),
    path("abmelden/", views.TeacherLogoutView.as_view(), name="logout"),
    path("anfrage/", views.access_request, name="access_request"),
    path("einladung/<str:token>/", views.invitation_accept, name="invitation_accept"),
]

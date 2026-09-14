from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("registrieren/", views.TeacherSignupView.as_view(), name="signup"),
    path("anmelden/", views.TeacherLoginView.as_view(), name="login"),
    path("abmelden/", views.TeacherLogoutView.as_view(), name="logout"),
]

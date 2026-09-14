from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .forms import TeacherSignupForm


class TeacherSignupView(CreateView):
    """Register a new teacher account and log them straight in."""

    form_class = TeacherSignupForm
    template_name = "accounts/signup.html"
    success_url = reverse_lazy("schools:dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("schools:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        login(
            self.request,
            self.object,
            backend="accounts.backends.EmailBackend",
        )
        messages.success(
            self.request,
            "Willkommen! Dein Lehrer-Konto wurde erfolgreich erstellt.",
        )
        return response


class TeacherLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


class TeacherLogoutView(LogoutView):
    pass

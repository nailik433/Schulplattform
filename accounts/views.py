from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import AccessRequestForm, InvitationAcceptForm
from .models import TeacherInvitation


class TeacherLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


class TeacherLogoutView(LogoutView):
    pass


def access_request(request):
    """A prospective teacher requests access to a school."""
    if request.user.is_authenticated:
        return redirect("schools:dashboard")

    if request.method == "POST":
        form = AccessRequestForm(request.POST)
        if form.is_valid():
            form.save()
            return render(request, "accounts/access_request_done.html")
    else:
        form = AccessRequestForm()
    return render(request, "accounts/access_request.html", {"form": form})


def invitation_accept(request, token):
    """Accept an invitation: set name + password, which creates the account."""
    if request.user.is_authenticated:
        return redirect("schools:dashboard")

    invitation = TeacherInvitation.objects.filter(token=token).select_related(
        "school"
    ).first()

    if invitation is None or not invitation.is_valid:
        return render(
            request,
            "accounts/invitation_invalid.html",
            {"invitation": invitation},
            status=410 if invitation else 404,
        )

    if request.method == "POST":
        form = InvitationAcceptForm(request.POST, invitation=invitation)
        if form.is_valid():
            user = form.save()
            invitation.accepted_at = timezone.now()
            invitation.save(update_fields=["accepted_at"])
            login(request, user, backend="accounts.backends.EmailBackend")
            messages.success(
                request,
                f"Willkommen! Dein Konto für {invitation.school.name} ist aktiv.",
            )
            return redirect("schools:dashboard")
    else:
        form = InvitationAcceptForm(invitation=invitation)

    return render(
        request,
        "accounts/invitation_accept.html",
        {"form": form, "invitation": invitation},
    )

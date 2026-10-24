from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import AccessRequestForm, InvitationAcceptForm
from .models import TeacherInvitation
from .throttling import client_ip, is_blocked, register_failure, reset


class TeacherLoginView(LoginView):
    """Email + password login with brute-force protection.

    Failed attempts are counted per client IP *and* per email address, so
    neither one attacker trying many accounts nor many attackers trying one
    account gets unlimited guesses. After the limit, logins are refused for
    an hour even with the correct password.
    """

    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    BLOCKED_MESSAGE = (
        "Zu viele Fehlversuche. Bitte warte eine Stunde oder setze dein "
        "Passwort zurück."
    )

    def _throttle_keys(self):
        keys = [f"teacher_login_fail:ip:{client_ip(self.request)}"]
        email = (self.request.POST.get("username") or "").strip().lower()
        if email:
            keys.append(f"teacher_login_fail:email:{email}")
        return keys

    def post(self, request, *args, **kwargs):
        if any(is_blocked(key) for key in self._throttle_keys()):
            # Do not even check the password while blocked: show the form
            # again with only the lock-out message.
            form = self.get_form_class()(request=request)
            form.full_clean()
            form.cleaned_data = {}  # add_error() expects it, even when unbound
            form.add_error(None, self.BLOCKED_MESSAGE)
            return self.render_to_response(self.get_context_data(form=form))
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        for key in self._throttle_keys():
            register_failure(key)
        return super().form_invalid(form)

    def form_valid(self, form):
        for key in self._throttle_keys():
            reset(key)
        return super().form_valid(form)


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

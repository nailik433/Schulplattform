from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """Authenticate teachers by email address (case-insensitive)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        email = username or kwargs.get("email")
        if email is None or password is None:
            return None
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # Run the default hasher once to reduce timing differences
            # between "unknown email" and "wrong password".
            User().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

"""Shared failed-attempt throttling for logins, backed by the Django cache.

Used by the student token login and the teacher password login so that
guessing attempts are limited per client. The configured cache is shared by
all gunicorn workers (see ``CACHES`` in settings), so the limit holds for the
whole server rather than per process.
"""

from django.core.cache import cache

DEFAULT_LIMIT = 10
DEFAULT_WINDOW = 3600  # seconds


def client_ip(request):
    """Best-effort client IP for rate limiting.

    Behind the Caddy reverse proxy the real client address is the *last*
    entry of ``X-Forwarded-For`` (Caddy appends it). Earlier entries can be
    forged by the client, so they are never trusted.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "")


def is_blocked(key, limit=DEFAULT_LIMIT):
    return cache.get(key, 0) >= limit


def register_failure(key, window=DEFAULT_WINDOW):
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, window)


def reset(key):
    cache.delete(key)

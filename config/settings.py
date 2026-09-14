"""
Django settings for the Schulplattform project.

Values that differ between development and production are read from
environment variables so the same code can run locally (SQLite, DEBUG on)
and on a rented server (Postgres, DEBUG off) without changes. See
``.env.example`` for the variables you can set in production.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    """Read a boolean-ish environment variable ("1", "true", "yes")."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    """Read a comma-separated environment variable into a list of strings."""
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# SECURITY WARNING: keep the secret key used in production secret!
# In production, set DJANGO_SECRET_KEY. The insecure fallback only applies
# in DEBUG mode so a forgotten variable fails loudly in production.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-yo#tmhv51@(w$)21snns$1!r=b86prgpl0$ax81io4&pybb)n@",
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env_bool("DJANGO_DEBUG", default=True)

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", default="localhost,127.0.0.1")

# Hosts that may submit forms (needed behind HTTPS on a real domain).
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# When running inside GitHub Codespaces (for a quick beta test without a
# rented server), make the app work over the forwarded *.app.github.dev URL
# out of the box: trust the host, trust the HTTPS origin for CSRF, and treat
# the request as secure. The Codespaces proxy terminates TLS and forwards to
# the dev server over plain HTTP, so without the last line Django would think
# the request is HTTP and reject form submissions (e.g. "Schule anlegen")
# with a CSRF error.
if DEBUG and os.environ.get("CODESPACES") == "true":
    _codespaces_domain = os.environ.get(
        "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "app.github.dev"
    )
    ALLOWED_HOSTS.append("." + _codespaces_domain)
    CSRF_TRUSTED_ORIGINS.append("https://*." + _codespaces_domain)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Local apps
    "accounts",
    "schools",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "schools.context_processors.current_student",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# Defaults to SQLite for local development. Set DATABASE_URL-style variables
# (DJANGO_DB_*) in production to use PostgreSQL instead.

if os.environ.get("DJANGO_DB_NAME"):
    DATABASES = {
        "default": {
            "ENGINE": os.environ.get(
                "DJANGO_DB_ENGINE", "django.db.backends.postgresql"
            ),
            "NAME": os.environ["DJANGO_DB_NAME"],
            "USER": os.environ.get("DJANGO_DB_USER", ""),
            "PASSWORD": os.environ.get("DJANGO_DB_PASSWORD", ""),
            "HOST": os.environ.get("DJANGO_DB_HOST", "localhost"),
            "PORT": os.environ.get("DJANGO_DB_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# Custom user model: teachers log in with their email address.
AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "accounts.backends.EmailBackend",
    "django.contrib.auth.backends.ModelBackend",
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "schools:dashboard"
LOGOUT_REDIRECT_URL = "home"


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
LANGUAGE_CODE = "de"
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Uploaded files (student submissions, worksheets in later stages)
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Security hardening that only takes effect in production (DEBUG off).
if not DEBUG:
    # Serve compressed, cache-busted static files straight from the app
    # (via WhiteNoise) so no extra static file server is required. Only
    # enabled when WhiteNoise is installed, so local development without it
    # keeps working unchanged.
    try:
        import whitenoise  # noqa: F401

        MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
        STORAGES["staticfiles"]["BACKEND"] = (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    except ImportError:
        pass

    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "2592000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    X_FRAME_OPTIONS = "DENY"

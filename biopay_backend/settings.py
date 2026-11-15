import os

from django.core.exceptions import ImproperlyConfigured

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY or SECRET_KEY == "replace-with-a-generated-secret":
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY to a generated secret.")

DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "payments",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
STATIC_URL = "static/"
# Same-origin by design: the Vite dev server proxies /api, so no CORS is configured.
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
ROOT_URLCONF = "biopay_backend.urls"
WSGI_APPLICATION = "biopay_backend.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"

# PostgreSQL only: SQLite cannot verify the locking used by this project.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("PGDATABASE", "biopay"),
        "USER": os.environ.get("PGUSER", "biopay"),
        "PASSWORD": os.environ.get("PGPASSWORD", ""),
        "HOST": os.environ.get("PGHOST", "127.0.0.1"),
        "PORT": os.environ.get("PGPORT", "5432"),
        "OPTIONS": {"connect_timeout": 5},
    }
}

BIOPAY_ENABLE_DEMO_API = os.environ.get("BIOPAY_ENABLE_DEMO_API", "false").lower() == "true"
# Real R307S terminals. Works with DEBUG off; mock enrollment/simulator stay DEBUG-only.
BIOPAY_TERMINAL_REAL_SENSOR = os.environ.get("BIOPAY_TERMINAL_REAL_SENSOR", "false").lower() == "true"
BIOPAY_DEMO_TOKEN = os.environ.get("BIOPAY_DEMO_TOKEN", "")
BIOPAY_SIGNUP_GRANT = int(os.environ.get("BIOPAY_SIGNUP_GRANT", "100"))
BIOPAY_MAX_PAYMENT = int(os.environ.get("BIOPAY_MAX_PAYMENT", "100"))
if not 1 <= BIOPAY_MAX_PAYMENT <= 2**63 - 1:
    raise ImproperlyConfigured("BIOPAY_MAX_PAYMENT must be a positive signed 64-bit integer.")
if BIOPAY_ENABLE_DEMO_API and len(BIOPAY_DEMO_TOKEN) < 32:
    raise ImproperlyConfigured("An enabled demo API requires BIOPAY_DEMO_TOKEN of at least 32 characters.")

REST_FRAMEWORK = {
    # Human web login. Demo and terminal views override this with their own credentials.
    "DEFAULT_AUTHENTICATION_CLASSES": ["payments.authentication.WebSessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "payments.api_errors.exception_handler",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_RATES": {"login": "10/min", "register": "10/hour"},
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

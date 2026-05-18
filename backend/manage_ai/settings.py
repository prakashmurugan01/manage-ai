from datetime import timedelta
from pathlib import Path
import os
from urllib.parse import urlparse, unquote

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env(name, default=None):
    return os.getenv(name, default)


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
railway_public_domain = env("RAILWAY_PUBLIC_DOMAIN", "")
allowed_hosts_default = "localhost,127.0.0.1"
if railway_public_domain:
    allowed_hosts_default = f"{allowed_hosts_default},{railway_public_domain}"
ALLOWED_HOSTS = [host.strip() for host in env("DJANGO_ALLOWED_HOSTS", allowed_hosts_default).split(",") if host.strip()]

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "django_filters",
    "corsheaders",
    "channels",
    "apps.accounts",
    "apps.projects",
    "apps.tasks",
    "apps.tickets",
    "apps.deployments",
    "apps.documents",
    "apps.notifications",
    "apps.audit",
    "apps.analytics",
    "apps.ai",
    "apps.enterprise",
    "apps.realtime",
    "apps.core",
    "apps.users",
    "apps.modules",
    "apps.crm",
    "apps.erp",
    "apps.hr",
    "apps.inventory",
    "apps.file_tracking",
    "apps.webhooks",
    "apps.ai_layer",
    "apps.server_monitor",
    "apps.api_keys",
    "apps.hosting",
    "apps.api_monitor",
    "apps.remote_access",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.api_keys.middleware.ApiKeyMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.audit.middleware.APIRequestLoggingMiddleware",
]

ROOT_URLCONF = "manage_ai.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "manage_ai.wsgi.application"
ASGI_APPLICATION = "manage_ai.asgi.application"

def database_from_url(database_url):
    parsed = urlparse(database_url)
    engine_by_scheme = {
        "postgres": "django.db.backends.postgresql",
        "postgresql": "django.db.backends.postgresql",
        "psql": "django.db.backends.postgresql",
        "sqlite": "django.db.backends.sqlite3",
    }
    engine = engine_by_scheme.get(parsed.scheme)
    if not engine:
        raise ValueError(f"Unsupported DATABASE_URL scheme: {parsed.scheme}")
    if engine == "django.db.backends.sqlite3":
        return {"ENGINE": engine, "NAME": unquote(parsed.path.lstrip("/")) or BASE_DIR / "manageai.sqlite3"}
    return {
        "ENGINE": engine,
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
        "CONN_MAX_AGE": int(env("DB_CONN_MAX_AGE", 600)),
    }


DATABASE_URL = env("DATABASE_URL")
DATABASES = {
    "default": database_from_url(DATABASE_URL)
    if DATABASE_URL
    else {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / env("DB_NAME", "manageai.sqlite3"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DATA_UPLOAD_MAX_MEMORY_SIZE = int(env("DATA_UPLOAD_MAX_MEMORY_SIZE", 5 * 1024 * 1024 * 1024))
FILE_UPLOAD_MAX_MEMORY_SIZE = int(env("FILE_UPLOAD_MAX_MEMORY_SIZE", 10 * 1024 * 1024))
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "URL_FORMAT_OVERRIDE": None,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(env("ACCESS_TOKEN_MINUTES", 30))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(env("REFRESH_TOKEN_DAYS", 7))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in env("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:5175,http://127.0.0.1:5175").split(",")
    if origin.strip()
]
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in env("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [env("REDIS_URL", "redis://127.0.0.1:6379/0")]},
    }
}

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env("REDIS_CACHE_URL", "redis://127.0.0.1:6379/1"),
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}

if env_bool("USE_INMEMORY_CHANNELS", False):
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

AI_PROVIDER = env("AI_PROVIDER", "local")
AI_ENABLED = env_bool("AI_ENABLED", False)
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", "")
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY", "")
GITHUB_TOKEN = env("GITHUB_TOKEN", "")
VERCEL_API_TOKEN = env("VERCEL_API_TOKEN", env("VERCEL_TOKEN", ""))
VERCEL_TEAM_ID = env("VERCEL_TEAM_ID", "")
VERCEL_CACHE_SECONDS = int(env("VERCEL_CACHE_SECONDS", 45))
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", env("AWS_ACCESS_KEY", ""))
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", env("AWS_SECRET_KEY", ""))
AWS_REGION = env("AWS_REGION", "us-east-1")
NETLIFY_API_TOKEN = env("NETLIFY_API_TOKEN", env("NETLIFY_TOKEN", ""))
CLOUDFLARE_API_TOKEN = env("CLOUDFLARE_API_TOKEN", "")
DIGITALOCEAN_API_TOKEN = env("DIGITALOCEAN_API_TOKEN", "")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "ManageAI <noreply@manageai.local>")
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")

SPECTACULAR_SETTINGS = {
    "TITLE": "Universal Connection Engine API",
    "DESCRIPTION": "Unified CRM, ERP, HR, Inventory, Project Management, event, and optional AI APIs.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

CELERY_BROKER_URL = env("CELERY_BROKER_URL", env("REDIS_URL", "redis://127.0.0.1:6379/0"))
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", DEBUG)
API_KEY_FERNET_KEY = env("API_KEY_FERNET_KEY", FIELD_ENCRYPTION_KEY)

from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "check-expiry-daily": {"task": "apps.notifications.tasks.check_hosting_expiry", "schedule": crontab(hour=9, minute=0)},
    "hosting-health-checks": {"task": "hosting.tasks.check_all_hosted_project_health", "schedule": 60.0},
    "hosting-vercel-sync": {"task": "hosting.tasks.sync_vercel_projects", "schedule": 60.0},
    "hosting-provider-sync": {"task": "hosting.tasks.sync_all_hosting_providers", "schedule": 120.0},
    "hosting-provider-failover": {"task": "hosting.tasks.evaluate_hosting_failover", "schedule": 60.0},
    "hosting-vercel-link-checks": {"task": "hosting.tasks.check_vercel_links", "schedule": 60.0},
    "hosting-vercel-deployment-alerts": {"task": "hosting.tasks.notify_failed_vercel_deployments", "schedule": 300.0},
    "hosting-lifecycle-statuses": {"task": "hosting.tasks.update_hosting_lifecycle_statuses", "schedule": crontab(hour=9, minute=10)},
    "collect-metrics": {"task": "apps.server_monitor.tasks.collect_server_metrics", "schedule": 60.0},
    "check-disk-alerts": {"task": "apps.server_monitor.tasks.check_disk_alerts", "schedule": 300.0},
    "broadcast-api-stats": {"task": "apps.api_monitor.tasks.broadcast_api_stats", "schedule": 10.0},
}

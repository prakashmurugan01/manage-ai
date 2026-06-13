from datetime import timedelta
from pathlib import Path
import os
import sys

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


def env_int(name, default):
    value = os.getenv(name)
    if value in {None, ""}:
        return default
    return int(value)


DEBUG = env_bool("DJANGO_DEBUG", True)
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-only-change-me" if DEBUG else "")
if not DEBUG and not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY is required when DJANGO_DEBUG=False")
ALLOWED_HOSTS = [host.strip() for host in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if host.strip()]

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
    "apps.project_intelligence",
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

DB_ENGINE = env("DB_ENGINE", "sqlite").lower()
if DB_ENGINE == "mysql":
    import pymysql

    pymysql.install_as_MySQLdb()
    mysql_options = {
        "charset": "utf8mb4",
        "init_command": env("DB_INIT_COMMAND", "SET sql_mode='STRICT_TRANS_TABLES'"),
    }
    if env("DB_SSL_CA"):
        mysql_options["ssl"] = {"ca": env("DB_SSL_CA")}
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": env("DB_NAME", "manageai"),
            "USER": env("DB_USER", "manageai"),
            "PASSWORD": env("DB_PASSWORD", ""),
            "HOST": env("DB_HOST", "127.0.0.1"),
            "PORT": env("DB_PORT", "3306"),
            "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 60),
            "OPTIONS": mysql_options,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / env("DB_NAME", "manageai.sqlite3"),
            "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 0),
            "OPTIONS": {"timeout": int(env("SQLITE_TIMEOUT_SECONDS", "20"))},
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
DESKTOP_TRANSFER_UPLOAD_ROOT = Path(env("DESKTOP_TRANSFER_UPLOAD_ROOT", MEDIA_ROOT / "desktop_transfer" / "uploads"))
DESKTOP_TRANSFER_TEMP_ROOT = Path(env("DESKTOP_TRANSFER_TEMP_ROOT", MEDIA_ROOT / "desktop_transfer" / "tmp"))
DESKTOP_TRANSFER_SERVER_ROOT = Path(env("DESKTOP_TRANSFER_SERVER_ROOT", MEDIA_ROOT / "server_storage" / "projects"))
DESKTOP_TRANSFER_ALLOW_ABSOLUTE_PATHS = env_bool("DESKTOP_TRANSFER_ALLOW_ABSOLUTE_PATHS", False)
DESKTOP_TRANSFER_MAX_FILE_SIZE = int(env("DESKTOP_TRANSFER_MAX_FILE_SIZE", 5 * 1024 * 1024 * 1024))
DESKTOP_TRANSFER_CHUNK_SIZE = int(env("DESKTOP_TRANSFER_CHUNK_SIZE", 2 * 1024 * 1024))
DESKTOP_TRANSFER_ALLOWED_EXTENSIONS = {
    ext.strip().lower()
    for ext in env(
        "DESKTOP_TRANSFER_ALLOWED_EXTENSIONS",
        ".zip,.tar,.gz,.sql,.json,.txt,.md,.py,.js,.jsx,.ts,.tsx,.html,.css,.png,.jpg,.jpeg,.pdf,.docx,.xlsx,.csv,.parquet,.bin,.msi,.conf,.env,.yml,.yaml,.xml",
    ).split(",")
    if ext.strip()
}
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

if not DEBUG:
    unsafe_hosts = {"*", "0.0.0.0"}
    if not ALLOWED_HOSTS or any(host in unsafe_hosts for host in ALLOWED_HOSTS):
        raise RuntimeError("DJANGO_ALLOWED_HOSTS must be explicit when DJANGO_DEBUG=False")
    if not CORS_ALLOWED_ORIGINS:
        raise RuntimeError("CORS_ALLOWED_ORIGINS is required when DJANGO_DEBUG=False")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", not DEBUG)
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", not DEBUG)
SECURE_HSTS_SECONDS = int(env("SECURE_HSTS_SECONDS", 31536000 if not DEBUG else 0))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", not DEBUG)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

if "test" in sys.argv:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

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
OPENAI_API_KEY = env("OPENAI_API_KEY", "")
OPENAI_MODEL = env("OPENAI_MODEL", "gpt-4o-mini")
GEMINI_API_KEY = env("GEMINI_API_KEY", env("GOOGLE_GEMINI_API_KEY", ""))
GEMINI_MODEL = env("GEMINI_MODEL", "gemini-1.5-flash")
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", "")
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY", "")
GITHUB_TOKEN = env("GITHUB_TOKEN", "")
VERCEL_API_TOKEN = env("VERCEL_API_TOKEN", env("VERCEL_TOKEN", ""))
VERCEL_TEAM_ID = env("VERCEL_TEAM_ID", "")
VERCEL_CACHE_SECONDS = int(env("VERCEL_CACHE_SECONDS", 45))
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", env("AWS_ACCESS_KEY", ""))
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", env("AWS_SECRET_KEY", ""))
AWS_REGION = env("AWS_REGION", "us-east-1")
AWS_DEPLOYMENT_BUCKET = env("AWS_DEPLOYMENT_BUCKET", env("AWS_STORAGE_BUCKET_NAME", ""))
AWS_DEPLOYMENT_URL = env("AWS_DEPLOYMENT_URL", "")
AWS_CLOUDFRONT_DISTRIBUTION_ID = env("AWS_CLOUDFRONT_DISTRIBUTION_ID", "")
AZURE_CLIENT_ID = env("AZURE_CLIENT_ID", "")
AZURE_CLIENT_SECRET = env("AZURE_CLIENT_SECRET", "")
AZURE_TENANT_ID = env("AZURE_TENANT_ID", "")
AZURE_SUBSCRIPTION_ID = env("AZURE_SUBSCRIPTION_ID", "")
AZURE_RESOURCE_GROUP = env("AZURE_RESOURCE_GROUP", "")
AZURE_APP_SERVICE_NAME = env("AZURE_APP_SERVICE_NAME", "")
AZURE_APP_SERVICE_URL = env("AZURE_APP_SERVICE_URL", "")
AZURE_KUDU_PUBLISH_URL = env("AZURE_KUDU_PUBLISH_URL", "")
GCP_PROJECT_ID = env("GCP_PROJECT_ID", "")
GCP_STORAGE_BUCKET = env("GCP_STORAGE_BUCKET", "")
GCP_DEPLOYMENT_URL = env("GCP_DEPLOYMENT_URL", "")
GCP_ACCESS_TOKEN = env("GCP_ACCESS_TOKEN", "")
GCP_SERVICE_ACCOUNT_JSON = env("GCP_SERVICE_ACCOUNT_JSON", "")
GOOGLE_APPLICATION_CREDENTIALS = env("GOOGLE_APPLICATION_CREDENTIALS", "")
NETLIFY_API_TOKEN = env("NETLIFY_API_TOKEN", env("NETLIFY_TOKEN", ""))
NETLIFY_SITE_ID = env("NETLIFY_SITE_ID", "")
CLOUDFLARE_API_TOKEN = env("CLOUDFLARE_API_TOKEN", "")
CLOUDFLARE_ACCOUNT_ID = env("CLOUDFLARE_ACCOUNT_ID", "")
CLOUDFLARE_PAGES_PROJECT_NAME = env("CLOUDFLARE_PAGES_PROJECT_NAME", "")
CLOUDFLARE_PAGES_BRANCH = env("CLOUDFLARE_PAGES_BRANCH", "main")
CLOUDFLARE_WRANGLER_BIN = env("CLOUDFLARE_WRANGLER_BIN", "npx --yes")
DIGITALOCEAN_API_TOKEN = env("DIGITALOCEAN_API_TOKEN", "")
HOSTINGER_API_TOKEN = env("HOSTINGER_API_TOKEN", "")
GODADDY_API_KEY = env("GODADDY_API_KEY", "")
GODADDY_API_SECRET = env("GODADDY_API_SECRET", "")
BLUEHOST_API_KEY = env("BLUEHOST_API_KEY", "")
SITEGROUND_API_TOKEN = env("SITEGROUND_API_TOKEN", "")
BIGROCK_API_KEY = env("BIGROCK_API_KEY", "")
CPANEL_API_TOKEN = env("CPANEL_API_TOKEN", "")
WHM_API_TOKEN = env("WHM_API_TOKEN", "")
PLESK_API_TOKEN = env("PLESK_API_TOKEN", "")
RAILWAY_API_TOKEN = env("RAILWAY_API_TOKEN", "")
RENDER_API_KEY = env("RENDER_API_KEY", "")
FIREBASE_SERVICE_ACCOUNT_JSON = env("FIREBASE_SERVICE_ACCOUNT_JSON", "")
SUPABASE_ACCESS_TOKEN = env("SUPABASE_ACCESS_TOKEN", "")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "ManageAI <noreply@manageai.local>")
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env("EMAIL_PORT", 25))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)

SPECTACULAR_SETTINGS = {
    "TITLE": "Universal Connection Engine API",
    "DESCRIPTION": "Unified CRM, ERP, HR, Inventory, Project Management, event, and optional AI APIs.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

CELERY_BROKER_URL = env("CELERY_BROKER_URL", env("REDIS_URL", "redis://127.0.0.1:6379/0"))
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", DEBUG)
CELERY_TIMEZONE = env("CELERY_TIMEZONE", TIME_ZONE)
API_KEY_FERNET_KEY = env("API_KEY_FERNET_KEY", FIELD_ENCRYPTION_KEY)

from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "check-expiry-daily": {"task": "apps.notifications.tasks.check_hosting_expiry", "schedule": crontab(hour=9, minute=0)},
    "hosting-health-checks": {"task": "hosting.tasks.check_all_hosted_project_health", "schedule": 30.0},
    "hosting-vercel-sync": {"task": "hosting.tasks.sync_vercel_projects", "schedule": 30.0},
    "hosting-provider-sync": {"task": "hosting.tasks.sync_all_hosting_providers", "schedule": 120.0},
    "hosting-provider-failover": {"task": "hosting.tasks.evaluate_hosting_failover", "schedule": 30.0},
    "hosting-vercel-link-checks": {"task": "hosting.tasks.check_vercel_links", "schedule": 30.0},
    "hosting-vercel-deployment-alerts": {"task": "hosting.tasks.notify_failed_vercel_deployments", "schedule": 300.0},
    "hosting-lifecycle-statuses": {"task": "hosting.tasks.update_hosting_lifecycle_statuses", "schedule": crontab(hour=9, minute=10)},
    "collect-metrics": {"task": "apps.server_monitor.tasks.collect_server_metrics", "schedule": 1.0},
    "check-disk-alerts": {"task": "apps.server_monitor.tasks.check_disk_alerts", "schedule": 300.0},
    "broadcast-api-stats": {"task": "apps.api_monitor.tasks.broadcast_api_stats", "schedule": 2.0},
    "project-intelligence-stale-agents": {"task": "apps.project_intelligence.tasks.mark_stale_project_agents", "schedule": 15.0},
}

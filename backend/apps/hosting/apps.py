from django.apps import AppConfig


class HostingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.hosting"

    def ready(self):
        from . import checks  # noqa: F401

from django.apps import apps
from django.db.utils import OperationalError, ProgrammingError

from apps.core.models import ModuleRegistry


def register_all_modules(**kwargs):
    for app_config in apps.get_app_configs():
        module_id = getattr(app_config, "module_id", None)
        if not module_id:
            continue
        try:
            ModuleRegistry.objects.update_or_create(
                module_id=module_id,
                defaults={
                    "display_name": getattr(app_config, "display_name", app_config.verbose_name),
                    "version": getattr(app_config, "version", "1.0.0"),
                    "schema": getattr(app_config, "schema", {}),
                    "capabilities": {"query_types": getattr(app_config, "supported_query_types", ["rest"])},
                    "endpoints": getattr(app_config, "endpoints", []),
                    "is_active": True,
                    "health_status": "healthy",
                },
            )
        except (OperationalError, ProgrammingError):
            return

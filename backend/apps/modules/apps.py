from django.apps import AppConfig


class ModulesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.modules"
    label = "modules"

    module_id = "modules"
    display_name = "Module Registry"
    version = "1.0.0"
    supported_query_types = ["rest", "nl"]
    schema = {
        "module_id": "slug",
        "display_name": "string",
        "schema": "json",
        "capabilities": "json",
        "health_status": "string",
    }

    def ready(self):
        from django.db.models.signals import post_migrate

        from apps.modules.registry import register_all_modules

        post_migrate.connect(register_all_modules, dispatch_uid="uce_register_all_modules")

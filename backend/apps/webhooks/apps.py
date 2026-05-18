from django.apps import AppConfig


class WebhooksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.webhooks"
    label = "webhooks"
    module_id = "webhooks"
    display_name = "Event Bus"
    version = "1.0.0"
    supported_query_types = ["rest"]
    schema = {"Event": {"event_type": "string", "source_module": "string", "payload": "json"}}


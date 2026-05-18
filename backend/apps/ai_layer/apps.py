from django.apps import AppConfig


class AiLayerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ai_layer"
    label = "ai_layer"
    module_id = "ai_layer"
    display_name = "AI Enhancement Layer"
    version = "1.0.0"
    supported_query_types = ["nl"]
    schema = {"AI_ENABLED": "boolean", "provider": "anthropic"}


from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.users"
    label = "uce_users"
    module_id = "users"
    display_name = "Users and RBAC"
    version = "1.0.0"
    supported_query_types = ["rest"]
    schema = {"Role": {"name": "string", "permissions": "json"}, "UserRoleAssignment": {"user": "uuid", "role": "uuid"}}


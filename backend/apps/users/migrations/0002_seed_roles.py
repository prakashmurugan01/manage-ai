from django.db import migrations


DEFAULT_PERMISSION_MATRIX = {
    "admin": {"*": ["create", "read", "update", "delete", "export"]},
    "manager": {"crm": ["create", "read", "update"], "erp": ["read"], "hr": ["read"], "inventory": ["read", "update"], "projects": ["create", "read", "update"]},
    "analyst": {"crm": ["read", "export"], "erp": ["read", "export"], "hr": ["read"], "inventory": ["read"], "projects": ["read", "export"]},
    "viewer": {"crm": ["read"], "erp": ["read"], "hr": ["read"], "inventory": ["read"], "projects": ["read"]},
}


def seed_roles(apps, schema_editor):
    Role = apps.get_model("uce_users", "Role")
    for name, display_name in [
        ("admin", "Admin"),
        ("manager", "Manager"),
        ("analyst", "Analyst"),
        ("viewer", "Viewer"),
    ]:
        Role.objects.update_or_create(
            name=name,
            defaults={"display_name": display_name, "permissions": DEFAULT_PERMISSION_MATRIX[name]},
        )


def remove_roles(apps, schema_editor):
    Role = apps.get_model("uce_users", "Role")
    Role.objects.filter(name__in=["admin", "manager", "analyst", "viewer"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("uce_users", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_roles, remove_roles),
    ]


from django.db import migrations


def seed_defaults(apps, schema_editor):
    Company = apps.get_model("enterprise", "Company")
    FeatureFlag = apps.get_model("enterprise", "FeatureFlag")
    ServerControlState = apps.get_model("enterprise", "ServerControlState")

    company, _ = Company.objects.get_or_create(
        slug="primary-company",
        defaults={"name": "Primary Company", "description": "Default isolated company workspace."},
    )
    ServerControlState.objects.get_or_create(company=company)
    flags = [
        ("task_manager", "Task Manager", "GLOBAL"),
        ("ai_chatbot", "AI Chatbot", "DEVELOPER"),
        ("notifications", "Notifications", "GLOBAL"),
        ("reports", "Reports", "ADMIN"),
        ("voice_assistant", "Voice Assistant", "GLOBAL"),
        ("face_login", "Face Recognition Login", "DEVELOPER"),
        ("crm", "CRM", "ADMIN"),
        ("erp", "ERP", "SUPER_ADMIN"),
    ]
    for key, label, dashboard in flags:
        FeatureFlag.objects.get_or_create(company=company, key=key, dashboard=dashboard, defaults={"label": label, "is_enabled": True})


class Migration(migrations.Migration):
    dependencies = [
        ("enterprise", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_defaults, migrations.RunPython.noop),
    ]

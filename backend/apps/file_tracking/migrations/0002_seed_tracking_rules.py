from django.db import migrations


def seed_rules(apps, schema_editor):
    TrackingRule = apps.get_model("file_tracking", "TrackingRule")
    TrackingRule.objects.update_or_create(
        name="Large transfer over 1GB",
        defaults={
            "rule_type": "large_transfer",
            "threshold_bytes": 1024 * 1024 * 1024,
            "severity": "high",
            "is_enabled": True,
        },
    )
    TrackingRule.objects.update_or_create(
        name="Sensitive extension movement",
        defaults={
            "rule_type": "sensitive_extension",
            "extensions": ["env", "key", "pem", "pfx", "sql", "bak"],
            "severity": "critical",
            "is_enabled": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("file_tracking", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_rules, migrations.RunPython.noop),
    ]


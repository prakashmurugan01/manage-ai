# Generated for Hosting Manager lifecycle and external API access.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("hosting", "0002_advanced_hosting_management"),
    ]

    operations = [
        migrations.AlterField(
            model_name="hostinglifecycle",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("created", "Created"),
                    ("updated", "Updated"),
                    ("renewed", "Renewed"),
                    ("suspended", "Suspended"),
                    ("reactivated", "Reactivated"),
                    ("expired", "Expired"),
                    ("platform_changed", "Platform changed"),
                    ("health_check", "Health check"),
                    ("link_disabled", "Link disabled"),
                    ("archived", "Archived"),
                    ("restored", "Restored"),
                    ("api_key_created", "API key created"),
                ],
                max_length=32,
            ),
        ),
        migrations.CreateModel(
            name="HostingProjectApiKey",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=160)),
                ("key_encrypted", models.TextField()),
                ("key_prefix", models.CharField(db_index=True, max_length=12)),
                ("role", models.CharField(choices=[("admin", "Admin"), ("client", "Client")], default="client", max_length=16)),
                ("rate_limit_per_minute", models.PositiveIntegerField(default=60)),
                ("is_active", models.BooleanField(default=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="hosting_api_keys", to=settings.AUTH_USER_MODEL),
                ),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="api_keys", to="hosting.hostedproject")),
            ],
            options={"ordering": ["project__name", "name"]},
        ),
        migrations.CreateModel(
            name="HostingApiUsageLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("endpoint", models.CharField(max_length=500)),
                ("http_method", models.CharField(max_length=12)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("response_code", models.PositiveIntegerField(default=200)),
                ("response_time_ms", models.PositiveIntegerField(default=0)),
                ("timestamp", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("api_key", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="usage_logs", to="hosting.hostingprojectapikey")),
            ],
            options={"ordering": ["-timestamp"], "indexes": [models.Index(fields=["api_key", "-timestamp"], name="hosting_hos_api_key_025ecb_idx")]},
        ),
    ]

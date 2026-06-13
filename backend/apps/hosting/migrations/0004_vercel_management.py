import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("hosting", "0003_lifecycle_api_keys_and_usage"),
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
                    ("link_enabled", "Link enabled"),
                    ("vercel_synced", "Vercel synced"),
                    ("vercel_redeploy", "Vercel redeploy"),
                    ("archived", "Archived"),
                    ("restored", "Restored"),
                    ("api_key_created", "API key created"),
                ],
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="hostingprojectapikey",
            name="permission_level",
            field=models.CharField(choices=[("read", "Read"), ("write", "Write")], default="read", max_length=16),
        ),
        migrations.CreateModel(
            name="VercelProject",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("vercel_id", models.CharField(db_index=True, max_length=80, unique=True)),
                ("name", models.CharField(db_index=True, max_length=180)),
                ("account_id", models.CharField(blank=True, max_length=120)),
                ("team_id", models.CharField(blank=True, max_length=120)),
                ("framework", models.CharField(blank=True, max_length=80)),
                ("production_domain", models.CharField(blank=True, max_length=255)),
                ("latest_deployment_id", models.CharField(blank=True, max_length=120)),
                ("latest_deployment_url", models.URLField(blank=True)),
                ("latest_deployment_status", models.CharField(blank=True, db_index=True, max_length=40)),
                ("raw", models.JSONField(blank=True, default=dict)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "hosted_project",
                    models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="vercel_project", to="hosting.hostedproject"),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="VercelProjectLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("domain", models.CharField(db_index=True, max_length=255)),
                ("url", models.URLField()),
                (
                    "tag",
                    models.CharField(choices=[("primary", "Primary"), ("backup", "Backup"), ("testing", "Testing"), ("preview", "Preview"), ("custom", "Custom")], db_index=True, default="custom", max_length=20),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("disabled_at", models.DateTimeField(blank=True, null=True)),
                ("last_http_status", models.PositiveIntegerField(blank=True, null=True)),
                ("response_time_ms", models.PositiveIntegerField(default=0)),
                ("uptime_percentage", models.DecimalField(decimal_places=2, default=100, max_digits=5)),
                ("last_checked_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="links", to="hosting.vercelproject")),
            ],
            options={"ordering": ["project__name", "tag", "domain"], "unique_together": {("project", "domain")}},
        ),
        migrations.CreateModel(
            name="VercelDeployment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("deployment_id", models.CharField(db_index=True, max_length=120, unique=True)),
                ("url", models.URLField(blank=True)),
                ("status", models.CharField(db_index=True, max_length=40)),
                ("target", models.CharField(blank=True, max_length=40)),
                ("meta", models.JSONField(blank=True, default=dict)),
                ("inspector_url", models.URLField(blank=True)),
                ("error_message", models.TextField(blank=True)),
                ("created_at_vercel", models.DateTimeField(blank=True, null=True)),
                ("ready_at", models.DateTimeField(blank=True, null=True)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("raw", models.JSONField(blank=True, default=dict)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="deployments", to="hosting.vercelproject")),
            ],
            options={"ordering": ["-created_at_vercel", "-id"]},
        ),
        migrations.CreateModel(
            name="HostingStatus",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_enabled", models.BooleanField(db_index=True, default=True)),
                ("mode", models.CharField(choices=[("active", "Active"), ("disabled", "Disabled")], default="active", max_length=20)),
                ("disabled_redirect_url", models.URLField(blank=True)),
                ("disabled_reason", models.TextField(blank=True)),
                ("last_action_at", models.DateTimeField(blank=True, null=True)),
                (
                    "last_action_by",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="vercel_hosting_actions", to=settings.AUTH_USER_MODEL),
                ),
                ("project", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="hosting_status", to="hosting.vercelproject")),
            ],
            options={"verbose_name_plural": "hosting statuses"},
        ),
    ]

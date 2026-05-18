import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hosting", "0004_vercel_management"),
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
                    ("failover", "Failover"),
                    ("provider_synced", "Provider synced"),
                    ("provider_toggled", "Provider toggled"),
                    ("vercel_synced", "Vercel synced"),
                    ("vercel_redeploy", "Vercel redeploy"),
                    ("archived", "Archived"),
                    ("restored", "Restored"),
                    ("api_key_created", "API key created"),
                ],
                max_length=32,
            ),
        ),
        migrations.CreateModel(
            name="HostingProvider",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("provider", models.CharField(choices=[("aws", "AWS"), ("netlify", "Netlify"), ("digitalocean", "DigitalOcean"), ("vercel", "Vercel")], db_index=True, max_length=24)),
                ("priority", models.PositiveSmallIntegerField(db_index=True, default=4)),
                ("is_enabled", models.BooleanField(default=True)),
                ("config", models.JSONField(blank=True, default=dict)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["priority", "provider", "name"], "unique_together": {("provider", "name")}},
        ),
        migrations.CreateModel(
            name="HostingLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(choices=[("aws", "AWS"), ("netlify", "Netlify"), ("digitalocean", "DigitalOcean"), ("vercel", "Vercel")], db_index=True, max_length=24)),
                ("priority", models.PositiveSmallIntegerField(db_index=True, default=4)),
                ("label", models.CharField(blank=True, max_length=160)),
                ("url", models.URLField(blank=True)),
                ("domain", models.CharField(blank=True, db_index=True, max_length=255)),
                ("external_id", models.CharField(blank=True, db_index=True, max_length=180)),
                ("region", models.CharField(blank=True, max_length=80)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("status", models.CharField(choices=[("on", "On"), ("off", "Off"), ("building", "Building"), ("error", "Error"), ("unknown", "Unknown")], db_index=True, default="unknown", max_length=20)),
                ("health_status", models.CharField(choices=[("healthy", "Healthy"), ("degraded", "Degraded"), ("down", "Down"), ("unknown", "Unknown")], db_index=True, default="unknown", max_length=20)),
                ("is_active", models.BooleanField(db_index=True, default=False)),
                ("is_enabled", models.BooleanField(default=True)),
                ("response_time_ms", models.PositiveIntegerField(default=0)),
                ("uptime_percentage", models.DecimalField(decimal_places=2, default=100, max_digits=5)),
                ("last_http_status", models.PositiveIntegerField(blank=True, null=True)),
                ("last_checked_at", models.DateTimeField(blank=True, null=True)),
                ("last_failover_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="hosting_links", to="hosting.hostedproject")),
                ("provider_config", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="links", to="hosting.hostingprovider")),
            ],
            options={"ordering": ["project__name", "priority", "provider", "label"], "indexes": [models.Index(fields=["project", "priority", "health_status"], name="hosting_hos_project_5ff445_idx")]},
        ),
        migrations.CreateModel(
            name="HostingFailoverState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("failover_enabled", models.BooleanField(default=True)),
                ("last_reason", models.TextField(blank=True)),
                ("last_evaluated_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("active_link", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="active_for_projects", to="hosting.hostinglink")),
                ("project", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="failover_state", to="hosting.hostedproject")),
            ],
            options={"ordering": ["project__name"]},
        ),
    ]

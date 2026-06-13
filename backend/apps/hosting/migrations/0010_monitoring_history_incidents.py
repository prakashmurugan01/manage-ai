from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("hosting", "0009_hostedproject_disabled_status"),
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
                    ("email_created", "Email created"),
                    ("email_deleted", "Email deleted"),
                    ("email_check", "Email check"),
                    ("domain_check", "Domain check"),
                    ("vercel_synced", "Vercel synced"),
                    ("vercel_redeploy", "Vercel redeploy"),
                    ("archived", "Archived"),
                    ("restored", "Restored"),
                    ("api_key_created", "API key created"),
                    ("incident_opened", "Incident opened"),
                    ("incident_resolved", "Incident resolved"),
                ],
                max_length=32,
            ),
        ),
        migrations.CreateModel(
            name="HostingHealthCheck",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("target_type", models.CharField(choices=[("project", "Project"), ("link", "Hosting link"), ("vercel_link", "Vercel link")], db_index=True, default="project", max_length=24)),
                ("url", models.URLField(blank=True)),
                ("final_url", models.URLField(blank=True)),
                ("status_code", models.PositiveIntegerField(blank=True, null=True)),
                ("response_time_ms", models.PositiveIntegerField(default=0)),
                ("is_online", models.BooleanField(db_index=True, default=False)),
                ("dns_ok", models.BooleanField(default=False)),
                ("ssl_ok", models.BooleanField(default=False)),
                ("ssl_expires_at", models.DateTimeField(blank=True, null=True)),
                ("redirect_chain", models.JSONField(blank=True, default=list)),
                ("error_message", models.TextField(blank=True)),
                ("checked_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("hosting_link", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="health_checks", to="hosting.hostinglink")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="health_checks", to="hosting.hostedproject")),
                ("vercel_link", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="health_checks", to="hosting.vercelprojectlink")),
            ],
            options={
                "ordering": ["-checked_at"],
                "indexes": [models.Index(fields=["project", "-checked_at"], name="hosting_hos_project_f88f23_idx"), models.Index(fields=["target_type", "is_online", "-checked_at"], name="hosting_hos_target__ea3df2_idx")],
            },
        ),
        migrations.CreateModel(
            name="HostingIncident",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("open", "Open"), ("resolved", "Resolved")], db_index=True, default="open", max_length=20)),
                ("failure_count", models.PositiveIntegerField(default=0)),
                ("started_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("last_status_code", models.PositiveIntegerField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
                ("downtime_seconds", models.PositiveIntegerField(default=0)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("hosting_link", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="incidents", to="hosting.hostinglink")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="incidents", to="hosting.hostedproject")),
                ("vercel_link", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="incidents", to="hosting.vercelprojectlink")),
            ],
            options={
                "ordering": ["-started_at"],
                "indexes": [models.Index(fields=["project", "status", "-started_at"], name="hosting_hos_project_f0307a_idx")],
            },
        ),
    ]

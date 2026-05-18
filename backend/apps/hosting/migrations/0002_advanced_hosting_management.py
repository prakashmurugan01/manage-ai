# Generated for advanced Hosting Manager fields.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hosting", "0001_initial"),
    ]

    operations = [
        migrations.AddField("hostedproject", "client_name", models.CharField(blank=True, db_index=True, max_length=180)),
        migrations.AddField("hostedproject", "server_ip", models.GenericIPAddressField(blank=True, null=True)),
        migrations.AddField("hostedproject", "access_key_encrypted", models.TextField(blank=True)),
        migrations.AddField("hostedproject", "access_key_prefix", models.CharField(blank=True, max_length=12)),
        migrations.AddField("hostedproject", "tag", models.CharField(db_index=True, default="active", max_length=32)),
        migrations.AddField(
            "hostedproject",
            "server_status",
            models.CharField(
                choices=[("online", "Online"), ("offline", "Offline"), ("slow", "Slow"), ("unknown", "Unknown")],
                db_index=True,
                default="unknown",
                max_length=24,
            ),
        ),
        migrations.AddField("hostedproject", "response_time_ms", models.PositiveIntegerField(default=0)),
        migrations.AddField("hostedproject", "uptime_percentage", models.DecimalField(decimal_places=2, default=100, max_digits=5)),
        migrations.AddField("hostedproject", "last_checked_at", models.DateTimeField(blank=True, null=True)),
        migrations.AddField("hostedproject", "check_interval_seconds", models.PositiveIntegerField(default=60)),
        migrations.AddField("hostedproject", "downtime_count", models.PositiveIntegerField(default=0)),
        migrations.AddField("hostedproject", "archived_at", models.DateTimeField(blank=True, null=True)),
        migrations.AlterField(
            "hostedproject",
            "status",
            models.CharField(
                choices=[
                    ("live", "Live"),
                    ("expired", "Expired"),
                    ("pending", "Pending"),
                    ("suspended", "Suspended"),
                    ("maintenance", "Maintenance"),
                ],
                db_index=True,
                default="pending",
                max_length=24,
            ),
        ),
        migrations.AlterField(
            "hostinglifecycle",
            "event_type",
            models.CharField(
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
                ],
                max_length=32,
            ),
        ),
    ]

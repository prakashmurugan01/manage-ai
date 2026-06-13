import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("hosting", "0010_monitoring_history_incidents"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectUploadSession",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("original_name", models.CharField(max_length=255)),
                ("source_type", models.CharField(db_index=True, default="file", max_length=32)),
                ("size_bytes", models.PositiveBigIntegerField(default=0)),
                ("chunk_size", models.PositiveIntegerField(default=5242880)),
                ("total_chunks", models.PositiveIntegerField(default=1)),
                ("received_chunks", models.JSONField(blank=True, default=list)),
                ("temp_dir", models.CharField(blank=True, max_length=500)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("uploading", "Uploading"),
                            ("completed", "Completed"),
                            ("cancelled", "Cancelled"),
                            ("failed", "Failed"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=24,
                    ),
                ),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("expires_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                (
                    "created_upload",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="upload_session",
                        to="hosting.projectupload",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="hosting_upload_sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="projectuploadsession",
            index=models.Index(fields=["owner", "status", "-created_at"], name="hosting_pro_owner_i_3a3650_idx"),
        ),
        migrations.AddIndex(
            model_name="projectuploadsession",
            index=models.Index(fields=["status", "expires_at"], name="hosting_pro_status_b24f92_idx"),
        ),
    ]

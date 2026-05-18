import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.hosting.models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("hosting", "0006_universal_hosting_email"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectUpload",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("original_name", models.CharField(max_length=255)),
                ("upload", models.FileField(upload_to=apps.hosting.models.deployment_upload_path)),
                ("size_bytes", models.PositiveBigIntegerField(default=0)),
                ("status", models.CharField(choices=[("uploaded", "Uploaded"), ("processing", "Processing"), ("analyzed", "Analyzed"), ("failed", "Failed")], db_index=True, default="uploaded", max_length=24)),
                ("project_type", models.CharField(blank=True, db_index=True, max_length=40)),
                ("detected_stack", models.JSONField(blank=True, default=list)),
                ("suggested_providers", models.JSONField(blank=True, default=list)),
                ("analysis", models.JSONField(blank=True, default=dict)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("analyzed_at", models.DateTimeField(blank=True, null=True)),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="hosting_uploads", to=settings.AUTH_USER_MODEL)),
                ("project", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="uploads", to="hosting.hostedproject")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="DeploymentRun",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("primary_provider", models.CharField(db_index=True, default="vercel", max_length=32)),
                ("backup_provider", models.CharField(blank=True, max_length=32)),
                ("domain", models.CharField(blank=True, max_length=255)),
                ("build_command", models.CharField(blank=True, max_length=255)),
                ("output_directory", models.CharField(blank=True, max_length=160)),
                ("environment", models.JSONField(blank=True, default=dict)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("uploading", "Uploading"), ("building", "Building"), ("deploying", "Deploying"), ("live", "Live"), ("error", "Error")], db_index=True, default="queued", max_length=24)),
                ("live_url", models.URLField(blank=True)),
                ("logs", models.JSONField(blank=True, default=list)),
                ("progress", models.PositiveSmallIntegerField(default=0)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="hosting_deployments", to=settings.AUTH_USER_MODEL)),
                ("project", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="deployment_runs", to="hosting.hostedproject")),
                ("upload", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="deployments", to="hosting.projectupload")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]

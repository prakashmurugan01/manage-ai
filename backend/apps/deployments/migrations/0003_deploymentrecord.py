from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("hosting", "0009_hostedproject_disabled_status"),
        ("projects", "0008_project_hosting_lifecycle_fields"),
        ("deployments", "0002_deploymentcontrol_commit_sha_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="DeploymentRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "project_name",
                    models.CharField(max_length=180),
                ),
                ("external_project_id", models.CharField(blank=True, max_length=80)),
                ("client_name", models.CharField(blank=True, max_length=180)),
                ("assigned_developer_name", models.CharField(blank=True, max_length=180)),
                ("deployment_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("hosting_provider", models.CharField(db_index=True, max_length=80)),
                ("domain", models.CharField(blank=True, db_index=True, max_length=255)),
                ("live_url", models.URLField(blank=True)),
                ("server_details", models.JSONField(blank=True, default=dict)),
                ("cost", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("renewal_cost", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("expiry_date", models.DateField(blank=True, db_index=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("QUEUED", "Queued"),
                            ("RUNNING", "Running"),
                            ("SUCCESS", "Success"),
                            ("FAILED", "Failed"),
                        ],
                        db_index=True,
                        default="QUEUED",
                        max_length=32,
                    ),
                ),
                ("deployment_logs", models.JSONField(blank=True, default=list)),
                ("pdf_documents", models.JSONField(blank=True, default=list)),
                ("configuration_files", models.JSONField(blank=True, default=list)),
                ("notes", models.TextField(blank=True)),
                (
                    "assigned_developer",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assigned_deployment_records", to=settings.AUTH_USER_MODEL),
                ),
                (
                    "created_by",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_deployment_records", to=settings.AUTH_USER_MODEL),
                ),
                (
                    "hosted_project",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="deployment_records", to="hosting.hostedproject"),
                ),
                (
                    "hosting_deployment",
                    models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="deployment_record", to="hosting.deploymentrun"),
                ),
                (
                    "project",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="deployment_records", to="projects.project"),
                ),
            ],
            options={
                "ordering": ["-deployment_at", "-created_at"],
                "indexes": [
                    models.Index(fields=["project", "-deployment_at"], name="deployment_project_65fa3a_idx"),
                    models.Index(fields=["hosting_provider", "status"], name="deployment_hosting_2f9f33_idx"),
                ],
            },
        ),
    ]

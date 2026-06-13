from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hosting", "0011_project_upload_session"),
    ]

    operations = [
        migrations.AlterField(
            model_name="deploymentrun",
            name="primary_provider",
            field=models.CharField(blank=True, db_index=True, default="", max_length=32),
        ),
        migrations.AlterField(
            model_name="deploymentrun",
            name="status",
            field=models.CharField(
                choices=[
                    ("idle", "Idle"),
                    ("queued", "Queued"),
                    ("uploading", "Uploading"),
                    ("analyzing", "Analyzing"),
                    ("configuring", "Configuring"),
                    ("building", "Building"),
                    ("deploying", "Deploying"),
                    ("verifying", "Verifying"),
                    ("live", "Live"),
                    ("failed", "Failed"),
                    ("error", "Error"),
                ],
                db_index=True,
                default="queued",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="deploymentrun",
            name="provider_deployment_id",
            field=models.CharField(blank=True, db_index=True, max_length=180),
        ),
        migrations.AddField(
            model_name="deploymentrun",
            name="build_id",
            field=models.CharField(blank=True, db_index=True, max_length=180),
        ),
        migrations.AddField(
            model_name="deploymentrun",
            name="metrics",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]

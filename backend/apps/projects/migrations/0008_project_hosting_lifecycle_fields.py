from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("hosting", "0005_multi_provider_hosting"),
        ("projects", "0007_uceproject_ucemilestone_ucetask_ucetimeentry_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="hosted_project",
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="management_project", to="hosting.hostedproject"),
        ),
        migrations.AddField(
            model_name="project",
            name="project_type",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="project",
            name="hosting_provider",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="project",
            name="hosting_package",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="project",
            name="server_details",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="project",
            name="domain_name",
            field=models.CharField(blank=True, db_index=True, max_length=255),
        ),
        migrations.AddField(
            model_name="project",
            name="ssl_info",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="project",
            name="hosting_start_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="project",
            name="hosting_expiry_date",
            field=models.DateField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="project",
            name="domain_expiry_date",
            field=models.DateField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="project",
            name="renewal_date",
            field=models.DateField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="project",
            name="project_cost",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="project",
            name="hosting_cost",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="project",
            name="renewal_cost",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="project",
            name="latest_deployment_status",
            field=models.CharField(choices=[("NOT_DEPLOYED", "Not deployed"), ("QUEUED", "Queued"), ("RUNNING", "Running"), ("DEPLOYED", "Deployed"), ("FAILED", "Failed"), ("ROLLED_BACK", "Rolled back")], default="NOT_DEPLOYED", max_length=32),
        ),
        migrations.AddField(
            model_name="project",
            name="latest_deployment_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="project",
            name="latest_deployment_url",
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name="project",
            name="system_status",
            field=models.CharField(choices=[("HEALTHY", "Healthy"), ("WARNING", "Warning"), ("DEGRADED", "Degraded"), ("DOWN", "Down"), ("EXPIRED", "Expired"), ("MAINTENANCE", "Maintenance")], default="HEALTHY", max_length=32),
        ),
        migrations.AddField(
            model_name="project",
            name="uptime_percentage",
            field=models.DecimalField(decimal_places=2, default=100, max_digits=5),
        ),
        migrations.AddField(
            model_name="project",
            name="lifecycle_metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]

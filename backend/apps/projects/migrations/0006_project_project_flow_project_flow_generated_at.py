from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0005_project_company"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="project_flow",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="project",
            name="flow_generated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

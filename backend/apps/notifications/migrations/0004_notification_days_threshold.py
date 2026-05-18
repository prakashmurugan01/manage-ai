# Generated for hosting reminder thresholds.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0003_notification_hosted_project_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="days_threshold",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]

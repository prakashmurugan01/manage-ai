from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hosting", "0008_expand_enterprise_provider_choices"),
    ]

    operations = [
        migrations.AlterField(
            model_name="hostedproject",
            name="status",
            field=models.CharField(
                choices=[
                    ("live", "Live"),
                    ("disabled", "Disabled"),
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
    ]

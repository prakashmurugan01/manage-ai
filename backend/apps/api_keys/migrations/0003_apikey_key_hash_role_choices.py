from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api_keys", "0002_secure_api_key_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="apikey",
            name="key_hash",
            field=models.CharField(blank=True, db_index=True, max_length=256),
        ),
        migrations.AlterField(
            model_name="apikey",
            name="role",
            field=models.CharField(
                choices=[
                    ("admin", "Admin"),
                    ("editor", "Editor"),
                    ("client", "Client (Legacy)"),
                    ("viewer", "Viewer"),
                ],
                default="viewer",
                max_length=16,
            ),
        ),
    ]

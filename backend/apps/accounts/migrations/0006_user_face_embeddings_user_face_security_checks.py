from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_user_face_enrolled_at_user_face_hash_user_face_image_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="face_embeddings",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="user",
            name="face_security_checks",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]

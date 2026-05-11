from django.db import migrations


def seed_face_login_flag(apps, schema_editor):
    Company = apps.get_model("enterprise", "Company")
    FeatureFlag = apps.get_model("enterprise", "FeatureFlag")
    company, _ = Company.objects.get_or_create(
        slug="primary-company",
        defaults={"name": "Primary Company", "description": "Default isolated company workspace."},
    )
    FeatureFlag.objects.update_or_create(
        company=company,
        key="face_login",
        dashboard="DEVELOPER",
        defaults={"label": "Face Recognition Login", "is_enabled": False, "config": {"optional": True}},
    )


class Migration(migrations.Migration):
    dependencies = [
        ("enterprise", "0005_projectestimate_demo_notes_projectestimate_demo_url_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_face_login_flag, migrations.RunPython.noop),
    ]

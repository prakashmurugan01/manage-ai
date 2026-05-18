from django.db import migrations, models
import uuid


def backfill_upload_ids(apps, schema_editor):
    transfer_model = apps.get_model("remote_access", "RemoteTransfer")
    for transfer in transfer_model.objects.filter(upload_id__isnull=True):
        transfer.upload_id = uuid.uuid4()
        transfer.save(update_fields=["upload_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("remote_access", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="remotetransfer",
            name="upload_id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="remotetransfer",
            name="original_name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="remotetransfer",
            name="stored_name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="remotetransfer",
            name="content_type",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name="remotetransfer",
            name="total_chunks",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="remotetransfer",
            name="completed_chunks",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="remotetransfer",
            name="storage_path",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="remotetransfer",
            name="chunk_size",
            field=models.PositiveIntegerField(default=1048576),
        ),
        migrations.RunPython(backfill_upload_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="remotetransfer",
            name="upload_id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]

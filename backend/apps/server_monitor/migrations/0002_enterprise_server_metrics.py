from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("server_monitor", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="server",
            name="connection_method",
            field=models.CharField(
                choices=[
                    ("local", "Local Agent"),
                    ("agent", "Remote Agent"),
                    ("ssh", "SSH"),
                    ("sftp", "SFTP"),
                    ("smb", "SMB"),
                    ("winrm", "WinRM"),
                    ("rest", "REST API"),
                    ("websocket", "WebSocket"),
                ],
                db_index=True,
                default="ssh",
                max_length=24,
            ),
        ),
        migrations.AddField(model_name="server", name="cpu_cores", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="server", name="health_score", field=models.PositiveSmallIntegerField(default=0)),
        migrations.AddField(model_name="server", name="hostname", field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name="server", name="last_error", field=models.TextField(blank=True)),
        migrations.AddField(model_name="server", name="last_heartbeat_at", field=models.DateTimeField(blank=True, db_index=True, null=True)),
        migrations.AddField(model_name="server", name="memory_total_gb", field=models.FloatField(default=0)),
        migrations.AddField(model_name="server", name="os_name", field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(model_name="server", name="os_version", field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(
            model_name="server",
            name="server_type",
            field=models.CharField(
                choices=[
                    ("local", "Local"),
                    ("windows", "Windows Server"),
                    ("linux", "Linux Server"),
                    ("vps", "VPS"),
                    ("dedicated", "Dedicated Server"),
                    ("physical", "Physical Server"),
                    ("cloud", "Cloud Server"),
                ],
                db_index=True,
                default="cloud",
                max_length=24,
            ),
        ),
        migrations.AddField(model_name="servermetrics", name="cpu_core_usage", field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name="servermetrics", name="cpu_temperature", field=models.FloatField(blank=True, null=True)),
        migrations.AddField(model_name="servermetrics", name="disk_read_bytes_per_sec", field=models.BigIntegerField(default=0)),
        migrations.AddField(model_name="servermetrics", name="disk_write_bytes_per_sec", field=models.BigIntegerField(default=0)),
        migrations.AddField(model_name="servermetrics", name="download_bytes_per_sec", field=models.BigIntegerField(default=0)),
        migrations.AddField(model_name="servermetrics", name="latency_ms", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="servermetrics", name="memory_cached_gb", field=models.FloatField(default=0)),
        migrations.AddField(model_name="servermetrics", name="memory_free_gb", field=models.FloatField(default=0)),
        migrations.AddField(model_name="servermetrics", name="memory_used_gb", field=models.FloatField(default=0)),
        migrations.AddField(model_name="servermetrics", name="packet_loss_percent", field=models.FloatField(default=0)),
        migrations.AddField(model_name="servermetrics", name="process_count", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="servermetrics", name="service_count", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="servermetrics", name="upload_bytes_per_sec", field=models.BigIntegerField(default=0)),
    ]

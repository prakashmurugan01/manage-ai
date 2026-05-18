# Generated manually for ManageAI remote access.

import django.db.models.deletion
import apps.remote_access.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RemoteDevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                ("hostname", models.CharField(blank=True, max_length=160)),
                ("platform", models.CharField(blank=True, max_length=80)),
                ("agent_version", models.CharField(blank=True, max_length=40)),
                ("token", models.CharField(default=apps.remote_access.models.make_token, max_length=128, unique=True)),
                ("fingerprint", models.CharField(blank=True, max_length=128)),
                ("public_key", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("ONLINE", "Online"), ("OFFLINE", "Offline"), ("BUSY", "Busy"), ("PENDING", "Pending approval")], default="OFFLINE", max_length=20)),
                ("capabilities", models.JSONField(blank=True, default=dict)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("last_seen_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="remote_devices", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-last_seen_at", "name"]},
        ),
        migrations.CreateModel(
            name="RemoteSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.CharField(default=apps.remote_access.models.make_token, max_length=128, unique=True)),
                ("status", models.CharField(choices=[("REQUESTED", "Requested"), ("APPROVED", "Approved"), ("ACTIVE", "Active"), ("ENDED", "Ended"), ("DENIED", "Denied"), ("EXPIRED", "Expired")], default="REQUESTED", max_length=20)),
                ("permission", models.CharField(choices=[("VIEW", "View only"), ("CONTROL", "Full control"), ("FILES", "File access"), ("ADMIN", "Full desktop and disk")], default="VIEW", max_length=20)),
                ("offer", models.JSONField(blank=True, default=dict)),
                ("answer", models.JSONField(blank=True, default=dict)),
                ("ice_candidates", models.JSONField(blank=True, default=list)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("device", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sessions", to="remote_access.remotedevice")),
                ("requested_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="remote_sessions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="RemoteTransfer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("direction", models.CharField(choices=[("DOWNLOAD", "Download"), ("UPLOAD", "Upload"), ("DEVICE_TO_DEVICE", "Device to device")], max_length=20)),
                ("source_path", models.TextField()),
                ("target_path", models.TextField(blank=True)),
                ("size_bytes", models.BigIntegerField(default=0)),
                ("transferred_bytes", models.BigIntegerField(default=0)),
                ("chunk_size", models.PositiveIntegerField(default=262144)),
                ("status", models.CharField(choices=[("QUEUED", "Queued"), ("RUNNING", "Running"), ("COMPLETED", "Completed"), ("FAILED", "Failed"), ("CANCELED", "Canceled")], default="QUEUED", max_length=20)),
                ("error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="transfers", to="remote_access.remotesession")),
            ],
        ),
        migrations.CreateModel(
            name="RemoteActivityLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(choices=[("DEVICE_ONLINE", "Device online"), ("DEVICE_OFFLINE", "Device offline"), ("SESSION_REQUEST", "Session request"), ("SESSION_APPROVED", "Session approved"), ("SESSION_DENIED", "Session denied"), ("SESSION_ENDED", "Session ended"), ("CONTROL", "Control input"), ("FILE_BROWSE", "File browse"), ("FILE_DOWNLOAD", "File download"), ("FILE_UPLOAD", "File upload"), ("FILE_DELETE", "File delete"), ("ERROR", "Error")], max_length=40)),
                ("message", models.CharField(max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("device", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="remote_access.remotedevice")),
                ("session", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="remote_access.remotesession")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]

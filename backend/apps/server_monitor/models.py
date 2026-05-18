from django.db import models


class Server(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        DOWN = "down", "Down"
        MAINTENANCE = "maintenance", "Maintenance"

    name = models.CharField(max_length=160)
    ip_address = models.GenericIPAddressField()
    ssh_port = models.PositiveIntegerField(default=22)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    is_enabled = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.ip_address})"


class ServerMetrics(models.Model):
    server = models.ForeignKey(Server, related_name="metrics", on_delete=models.CASCADE)
    cpu_percent = models.FloatField(default=0)
    memory_percent = models.FloatField(default=0)
    disk_percent = models.FloatField(default=0)
    uptime_seconds = models.BigIntegerField(default=0)
    network_bytes_sent = models.BigIntegerField(default=0)
    network_bytes_recv = models.BigIntegerField(default=0)
    recorded_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-recorded_at"]
        indexes = [models.Index(fields=["server", "-recorded_at"])]


class DiskMount(models.Model):
    server = models.ForeignKey(Server, related_name="disk_mounts", on_delete=models.CASCADE)
    mount_point = models.CharField(max_length=255)
    total_gb = models.FloatField(default=0)
    used_gb = models.FloatField(default=0)
    free_gb = models.FloatField(default=0)
    usage_percent = models.FloatField(default=0)
    alert_threshold = models.FloatField(default=90)
    recorded_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["server", "mount_point"]
        indexes = [models.Index(fields=["server", "mount_point", "-recorded_at"])]


from django.db import models


class Server(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        DOWN = "down", "Down"
        MAINTENANCE = "maintenance", "Maintenance"

    class ServerType(models.TextChoices):
        LOCAL = "local", "Local"
        WINDOWS = "windows", "Windows Server"
        LINUX = "linux", "Linux Server"
        VPS = "vps", "VPS"
        DEDICATED = "dedicated", "Dedicated Server"
        PHYSICAL = "physical", "Physical Server"
        CLOUD = "cloud", "Cloud Server"

    class ConnectionMethod(models.TextChoices):
        LOCAL = "local", "Local Agent"
        AGENT = "agent", "Remote Agent"
        SSH = "ssh", "SSH"
        SFTP = "sftp", "SFTP"
        SMB = "smb", "SMB"
        WINRM = "winrm", "WinRM"
        REST = "rest", "REST API"
        WEBSOCKET = "websocket", "WebSocket"

    name = models.CharField(max_length=160)
    ip_address = models.GenericIPAddressField()
    hostname = models.CharField(max_length=255, blank=True)
    server_type = models.CharField(max_length=24, choices=ServerType.choices, default=ServerType.CLOUD, db_index=True)
    connection_method = models.CharField(max_length=24, choices=ConnectionMethod.choices, default=ConnectionMethod.SSH, db_index=True)
    ssh_port = models.PositiveIntegerField(default=22)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    is_enabled = models.BooleanField(default=True)
    os_name = models.CharField(max_length=120, blank=True)
    os_version = models.CharField(max_length=255, blank=True)
    cpu_cores = models.PositiveIntegerField(default=0)
    memory_total_gb = models.FloatField(default=0)
    health_score = models.PositiveSmallIntegerField(default=0)
    last_heartbeat_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_error = models.TextField(blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.ip_address})"


class ServerMetrics(models.Model):
    server = models.ForeignKey(Server, related_name="metrics", on_delete=models.CASCADE)
    cpu_percent = models.FloatField(default=0)
    cpu_temperature = models.FloatField(null=True, blank=True)
    cpu_core_usage = models.JSONField(default=list, blank=True)
    memory_percent = models.FloatField(default=0)
    memory_used_gb = models.FloatField(default=0)
    memory_free_gb = models.FloatField(default=0)
    memory_cached_gb = models.FloatField(default=0)
    disk_percent = models.FloatField(default=0)
    disk_read_bytes_per_sec = models.BigIntegerField(default=0)
    disk_write_bytes_per_sec = models.BigIntegerField(default=0)
    uptime_seconds = models.BigIntegerField(default=0)
    network_bytes_sent = models.BigIntegerField(default=0)
    network_bytes_recv = models.BigIntegerField(default=0)
    upload_bytes_per_sec = models.BigIntegerField(default=0)
    download_bytes_per_sec = models.BigIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    packet_loss_percent = models.FloatField(default=0)
    process_count = models.PositiveIntegerField(default=0)
    service_count = models.PositiveIntegerField(default=0)
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

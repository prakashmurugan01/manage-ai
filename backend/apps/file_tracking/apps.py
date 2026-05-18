from django.apps import AppConfig


class FileTrackingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.file_tracking"
    label = "file_tracking"
    module_id = "file_tracking"
    display_name = "Disk-to-Disk File Tracking"
    version = "1.0.0"
    supported_query_types = ["rest", "nl"]
    schema = {
        "DiskVolume": {"label": "string", "mount_path": "string", "total_bytes": "integer", "used_bytes": "integer"},
        "FileTransfer": {"file_name": "string", "source_path": "string", "destination_path": "string", "size_bytes": "integer"},
        "FileEvent": {"event_type": "string", "transfer": "uuid", "payload": "json"},
        "FileAlert": {"severity": "string", "status": "string", "message": "string"},
        "TrackingRule": {"name": "string", "threshold_bytes": "integer", "is_enabled": "boolean"},
    }
    endpoints = [
        "/api/v1/file-tracking/dashboard/",
        "/api/v1/file-tracking/transfers/",
        "/api/v1/file-tracking/events/",
        "/api/v1/file-tracking/alerts/",
        "/api/v1/file-tracking/rules/",
    ]

    def ready(self):
        from apps.file_tracking import signals  # noqa: F401


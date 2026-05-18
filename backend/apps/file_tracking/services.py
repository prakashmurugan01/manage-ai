import mimetypes
from pathlib import Path

from django.db.models import Count, Sum
from django.utils import timezone

from apps.file_tracking.models import DiskVolume, FileAlert, FileEvent, FileTransfer, TrackingRule
from apps.webhooks.services import emit_event


def infer_extension(path):
    suffix = Path(path or "").suffix.lower()
    return suffix[1:] if suffix.startswith(".") else suffix


def infer_mime_type(path):
    return mimetypes.guess_type(path or "")[0] or ""


def get_or_create_volume(path, label=None, disk_type=DiskVolume.DiskType.LOCAL):
    root = infer_volume_root(path)
    volume, _ = DiskVolume.objects.get_or_create(
        mount_path=root,
        defaults={
            "label": label or root,
            "disk_type": disk_type,
            "last_seen_at": timezone.now(),
        },
    )
    return volume


def infer_volume_root(path):
    value = str(path or "").replace("\\", "/")
    if len(value) >= 2 and value[1] == ":":
        return value[:2].upper()
    if value.startswith("//"):
        parts = value.strip("/").split("/")
        return f"//{parts[0]}/{parts[1]}" if len(parts) >= 2 else value
    parts = value.strip("/").split("/")
    return f"/{parts[0]}" if parts and parts[0] else "/"


def record_transfer(payload, user=None):
    source_path = payload["source_path"]
    destination_path = payload["destination_path"]
    source_volume = get_or_create_volume(source_path, payload.get("source_label"), payload.get("source_disk_type", DiskVolume.DiskType.LOCAL))
    destination_volume = get_or_create_volume(destination_path, payload.get("destination_label"), payload.get("destination_disk_type", DiskVolume.DiskType.LOCAL))
    file_name = payload.get("file_name") or Path(destination_path).name or Path(source_path).name
    status = payload.get("status", FileTransfer.Status.DETECTED)
    transfer = FileTransfer.objects.create(
        file_name=file_name,
        file_extension=payload.get("file_extension") or infer_extension(file_name),
        mime_type=payload.get("mime_type") or infer_mime_type(file_name),
        checksum=payload.get("checksum", ""),
        size_bytes=payload.get("size_bytes", 0),
        source_volume=source_volume,
        destination_volume=destination_volume,
        source_path=source_path,
        destination_path=destination_path,
        status=status,
        started_at=payload.get("started_at") or timezone.now(),
        completed_at=payload.get("completed_at") if status == FileTransfer.Status.COMPLETED else None,
        duration_ms=payload.get("duration_ms"),
        initiated_by=user if getattr(user, "is_authenticated", False) else None,
        process_name=payload.get("process_name", ""),
        metadata=payload.get("metadata", {}),
    )
    FileEvent.objects.create(
        event_type=FileEvent.EventType.MOVED,
        transfer=transfer,
        source_path=source_path,
        destination_path=destination_path,
        payload={"status": status, "size_bytes": transfer.size_bytes},
        observed_at=timezone.now(),
    )
    evaluate_transfer_rules(transfer)
    emit_event(
        "file_transfer_recorded",
        "file_tracking",
        "FileTransfer",
        str(transfer.id),
        {
            "file_name": transfer.file_name,
            "size_bytes": transfer.size_bytes,
            "source": transfer.source_path,
            "destination": transfer.destination_path,
            "status": transfer.status,
        },
    )
    return transfer


def evaluate_transfer_rules(transfer):
    for rule in TrackingRule.objects.filter(is_deleted=False, is_enabled=True):
        if rule.rule_type == TrackingRule.RuleType.LARGE_TRANSFER and transfer.size_bytes >= rule.threshold_bytes:
            create_alert(transfer, rule, f"Large file transfer detected: {transfer.file_name}")
        if rule.rule_type == TrackingRule.RuleType.SENSITIVE_EXTENSION and transfer.file_extension.lower() in [ext.lower().lstrip(".") for ext in rule.extensions]:
            create_alert(transfer, rule, f"Sensitive file extension moved: .{transfer.file_extension}")
    transfer.risk_score = min(100, transfer.alerts.filter(is_deleted=False).count() * 35)
    transfer.save(update_fields=["risk_score", "updated_at"])


def create_alert(transfer, rule, message):
    alert, _ = FileAlert.objects.get_or_create(
        transfer=transfer,
        rule=rule,
        message=message,
        defaults={
            "severity": rule.severity,
            "details": {
                "file_name": transfer.file_name,
                "size_bytes": transfer.size_bytes,
                "source_path": transfer.source_path,
                "destination_path": transfer.destination_path,
            },
        },
    )
    emit_event("file_alert_created", "file_tracking", "FileAlert", str(alert.id), {"message": alert.message, "severity": alert.severity})
    return alert


def dashboard_summary():
    transfers = FileTransfer.objects.filter(is_deleted=False)
    alerts = FileAlert.objects.filter(is_deleted=False)
    volumes = DiskVolume.objects.filter(is_deleted=False)
    by_status = dict(transfers.values_list("status").annotate(total=Count("id")))
    by_extension = list(transfers.values("file_extension").annotate(total=Count("id"), bytes=Sum("size_bytes")).order_by("-bytes")[:10])
    volume_usage = [
        {
            "id": str(volume.id),
            "label": volume.label,
            "mount_path": volume.mount_path,
            "disk_type": volume.disk_type,
            "used_bytes": volume.used_bytes,
            "free_bytes": volume.free_bytes,
            "total_bytes": volume.total_bytes,
            "is_online": volume.is_online,
        }
        for volume in volumes
    ]
    return {
        "totals": {
            "transfers": transfers.count(),
            "bytes_moved": transfers.aggregate(total=Sum("size_bytes"))["total"] or 0,
            "open_alerts": alerts.filter(status=FileAlert.Status.OPEN).count(),
            "volumes": volumes.count(),
        },
        "by_status": by_status,
        "by_extension": by_extension,
        "volume_usage": volume_usage,
        "recent_transfers": list(
            transfers.select_related("source_volume", "destination_volume")
            .values("id", "file_name", "size_bytes", "source_path", "destination_path", "status", "created_at", "risk_score")[:12]
        ),
        "recent_alerts": list(alerts.values("id", "severity", "status", "message", "created_at")[:12]),
    }


import hashlib
import mimetypes
import shutil
import time
import uuid
from pathlib import Path

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.utils.text import get_valid_filename
from django.utils import timezone

from apps.file_tracking.models import (
    ChunkUploadSession,
    DesktopDevice,
    DesktopTransferAuditLog,
    DesktopTransferJob,
    DeviceConnection,
    DiskVolume,
    FileAlert,
    FileEvent,
    FileTransfer,
    PhysicalStorageFile,
    ProjectFile,
    TrackingRule,
)
from apps.webhooks.services import emit_event


def infer_extension(path):
    suffix = Path(path or "").suffix.lower()
    return suffix[1:] if suffix.startswith(".") else suffix


def infer_mime_type(path):
    return mimetypes.guess_type(path or "")[0] or ""


def ensure_transfer_directories():
    for path in [settings.DESKTOP_TRANSFER_UPLOAD_ROOT, settings.DESKTOP_TRANSFER_TEMP_ROOT, settings.DESKTOP_TRANSFER_SERVER_ROOT]:
        Path(path).mkdir(parents=True, exist_ok=True)


def sanitize_relative_path(value):
    parts = []
    for part in str(value or "").replace("\\", "/").split("/"):
        if not part or part in {".", ".."}:
            continue
        parts.append(get_valid_filename(part))
    return Path(*parts) if parts else Path()


def safe_storage_path(raw_path=None, device_id=None):
    ensure_transfer_directories()
    root = Path(settings.DESKTOP_TRANSFER_SERVER_ROOT).resolve()
    value = str(raw_path or "").strip()
    if not value:
        return root / get_valid_filename(device_id or "default")
    normalized = value.replace("\\", "/").rstrip("/")
    if normalized in {"/server_storage/projects", "server_storage/projects"}:
        return root
    if normalized.startswith("/server_storage/projects/"):
        return root / sanitize_relative_path(normalized.removeprefix("/server_storage/projects/"))
    candidate = Path(value)
    if candidate.is_absolute():
        if settings.DESKTOP_TRANSFER_ALLOW_ABSOLUTE_PATHS:
            return candidate
        return root / get_valid_filename(candidate.name or device_id or "device")
    return root / sanitize_relative_path(value)


def safe_child_path(base_path, requested_name):
    base = Path(base_path).resolve()
    child = (base / sanitize_relative_path(requested_name)).resolve()
    if base != child and base not in child.parents:
        raise ValueError("Path escapes the configured storage root.")
    return child


def unique_destination_path(directory, filename):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    safe_name = get_valid_filename(filename or "file.bin")
    candidate = directory / safe_name
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    for index in range(1, 10000):
        next_candidate = directory / f"{stem}-{index}{suffix}"
        if not next_candidate.exists():
            return next_candidate
    return directory / f"{stem}-{uuid.uuid4().hex[:8]}{suffix}"


def hash_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_transfer_file(file_name, total_size):
    if total_size and int(total_size) > settings.DESKTOP_TRANSFER_MAX_FILE_SIZE:
        raise ValueError(f"File exceeds configured limit of {settings.DESKTOP_TRANSFER_MAX_FILE_SIZE} bytes.")
    extension = Path(file_name or "").suffix.lower()
    allowed = getattr(settings, "DESKTOP_TRANSFER_ALLOWED_EXTENSIONS", set())
    if allowed and extension and extension not in allowed:
        raise ValueError(f"File type {extension} is not allowed.")
    if allowed and not extension:
        raise ValueError("Files without an extension are not allowed.")


def broadcast_desktop_event(event_type, payload):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            "desktop_transfer",
            {
                "type": "desktop.event",
                "event": {
                    "type": event_type,
                    "payload": payload,
                    "created_at": timezone.now().isoformat(),
                },
            },
        )
    except Exception:
        pass


def write_audit(action, message, actor=None, device=None, project_file=None, transfer_job=None, metadata=None):
    log = DesktopTransferAuditLog.objects.create(
        action=action,
        message=message,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        device=device,
        project_file=project_file,
        transfer_job=transfer_job,
        metadata=metadata or {},
    )
    broadcast_desktop_event("audit", {"id": str(log.id), "action": action, "message": message})
    return log


def notify_admins(title, message, sender=None):
    try:
        from apps.notifications.services import broadcast_notification, notify_user

        user_model = get_user_model()
        admins = user_model.objects.filter(role__in=[user_model.Role.SUPER_ADMIN, user_model.Role.ADMIN], is_active=True)
        for admin in admins:
            notification = notify_user(admin, title, message, sender=sender, type="FILE", urgency="info")
            broadcast_notification(notification)
    except Exception:
        pass


def can_admin_transfer(user):
    return bool(
        getattr(user, "is_superuser", False)
        or getattr(user, "is_staff", False)
        or getattr(user, "role", "") in {"SUPER_ADMIN", "ADMIN"}
    )


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


def register_device(payload, user):
    device_id = payload.get("device_id") or f"DEV-{uuid.uuid4().hex[:10].upper()}"
    storage_path = safe_storage_path(payload.get("storage_path"), device_id)
    storage_path.mkdir(parents=True, exist_ok=True)
    defaults = {
        "name": payload.get("name") or device_id,
        "device_type": payload.get("device_type", DesktopDevice.DeviceType.DESKTOP),
        "ip_address": payload.get("ip_address") or None,
        "mac_address": payload.get("mac_address", ""),
        "os_name": payload.get("os_name", ""),
        "status": DesktopDevice.Status.ONLINE,
        "storage_path": str(storage_path),
        "total_storage_bytes": payload.get("total_storage_bytes", 0) or 0,
        "used_storage_bytes": payload.get("used_storage_bytes", 0) or 0,
        "cpu_percent": payload.get("cpu_percent", 0) or 0,
        "ram_percent": payload.get("ram_percent", 0) or 0,
        "disk_percent": payload.get("disk_percent", 0) or 0,
        "transfer_status": payload.get("transfer_status", "idle"),
        "last_seen_at": timezone.now(),
        "owner": user if getattr(user, "is_authenticated", False) else None,
        "metadata": payload.get("metadata", {}),
    }
    device, created = DesktopDevice.objects.update_or_create(device_id=device_id, defaults=defaults)
    write_audit("device_registered" if created else "device_heartbeat", f"{device.name} is online", actor=user, device=device)
    broadcast_desktop_event("device.updated", {"id": str(device.id), "device_id": device.device_id, "name": device.name, "status": device.status})
    return device


def set_connection_status(connection, status_value, user=None):
    now = timezone.now()
    connection.status = status_value
    connection.connected_by = user if getattr(user, "is_authenticated", False) else connection.connected_by
    if status_value == DeviceConnection.Status.CONNECTED:
        connection.connected_at = now
        connection.disconnected_at = None
    if status_value == DeviceConnection.Status.DISCONNECTED:
        connection.disconnected_at = now
    connection.save(update_fields=["status", "connected_by", "connected_at", "disconnected_at", "updated_at"])
    write_audit(
        "device_connection",
        f"{connection.source_device.name} -> {connection.destination_device.name}: {connection.status}",
        actor=user,
        device=connection.source_device,
        metadata={"connection_id": str(connection.id)},
    )
    broadcast_desktop_event(
        "connection.updated",
        {
            "id": str(connection.id),
            "source_device": str(connection.source_device_id),
            "destination_device": str(connection.destination_device_id),
            "status": connection.status,
        },
    )
    return connection


def handle_chunk_upload(payload, chunk_file, user):
    ensure_transfer_directories()
    upload_id = payload.get("upload_id") or uuid.uuid4().hex
    file_name = payload.get("file_name") or getattr(chunk_file, "name", "upload.bin")
    total_size = int(payload.get("total_size") or 0)
    total_chunks = max(1, int(payload.get("total_chunks") or 1))
    chunk_index = int(payload.get("chunk_index") or 0)
    relative_path = str(payload.get("relative_path") or "")
    validate_transfer_file(file_name, total_size)
    if chunk_index < 0 or chunk_index >= total_chunks:
        raise ValueError("Invalid chunk index.")
    source_device = DesktopDevice.objects.filter(id=payload.get("source_device")).first() or DesktopDevice.objects.filter(device_id=payload.get("source_device")).first()
    destination_device = DesktopDevice.objects.filter(id=payload.get("destination_device")).first() or DesktopDevice.objects.filter(device_id=payload.get("destination_device")).first()
    temp_dir = Path(settings.DESKTOP_TRANSFER_TEMP_ROOT) / get_valid_filename(upload_id)
    temp_dir.mkdir(parents=True, exist_ok=True)
    session, _ = ChunkUploadSession.objects.get_or_create(
        upload_id=upload_id,
        defaults={
            "file_name": file_name,
            "relative_path": relative_path,
            "total_size": total_size,
            "total_chunks": total_chunks,
            "temp_dir": str(temp_dir),
            "source_device": source_device,
            "destination_device": destination_device,
            "uploaded_by": user,
            "metadata": {"encrypted": True, "transport": "chunked"},
        },
    )
    chunk_path = temp_dir / f"{chunk_index:08d}.part"
    with open(chunk_path, "wb") as destination:
        for chunk in chunk_file.chunks():
            destination.write(chunk)
    received = set(session.received_chunks or [])
    received.add(chunk_index)
    session.received_chunks = sorted(received)
    session.total_chunks = total_chunks
    session.total_size = total_size
    session.source_device = source_device
    session.destination_device = destination_device
    session.save(update_fields=["received_chunks", "total_chunks", "total_size", "source_device", "destination_device", "updated_at"])
    progress = round((len(received) / total_chunks) * 100, 2)
    broadcast_desktop_event(
        "upload.progress",
        {
            "upload_id": upload_id,
            "file_name": file_name,
            "progress": progress,
            "received_chunks": len(received),
            "total_chunks": total_chunks,
        },
    )
    if len(received) < total_chunks:
        return session, None
    project_file = assemble_upload_session(session, user)
    session.status = ChunkUploadSession.Status.COMPLETED
    session.project_file = project_file
    session.save(update_fields=["status", "project_file", "updated_at"])
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass
    if payload.get("auto_transfer") in {True, "true", "1", 1} and destination_device and can_admin_transfer(user):
        deploy_project_file(project_file, destination_device, user, approved_by=user)
    return session, project_file


def assemble_upload_session(session, user):
    final_dir = Path(settings.DESKTOP_TRANSFER_UPLOAD_ROOT) / str(user.id)
    relative_parent = sanitize_relative_path(Path(session.relative_path).parent if session.relative_path else "")
    final_dir = final_dir / relative_parent
    final_dir.mkdir(parents=True, exist_ok=True)
    final_path = unique_destination_path(final_dir, session.file_name)
    with open(final_path, "wb") as output:
        for index in range(session.total_chunks):
            chunk_path = Path(session.temp_dir) / f"{index:08d}.part"
            if not chunk_path.exists():
                raise ValueError(f"Missing chunk {index}.")
            with open(chunk_path, "rb") as input_chunk:
                shutil.copyfileobj(input_chunk, output)
    checksum = hash_file(final_path)
    risk_score = calculate_risk_score(session.file_name, session.total_size)
    project_file = ProjectFile.objects.create(
        original_name=session.file_name,
        stored_name=final_path.name,
        relative_path=session.relative_path,
        storage_path=str(final_path),
        content_type=infer_mime_type(session.file_name),
        extension=infer_extension(session.file_name),
        size_bytes=final_path.stat().st_size,
        checksum=checksum,
        status=ProjectFile.Status.PENDING,
        source_device=session.source_device,
        destination_device=session.destination_device,
        uploaded_by=user,
        security_scan_status="clean" if risk_score < 70 else "review",
        risk_score=risk_score,
        metadata={"encrypted_transfer": True, "chunk_upload_id": session.upload_id},
    )
    write_audit("file_uploaded", f"{project_file.original_name} uploaded for review", actor=user, device=session.source_device, project_file=project_file)
    notify_admins("New project file awaiting approval", f"{project_file.original_name} was uploaded by {getattr(user, 'email', user)}.", sender=user)
    broadcast_desktop_event("project_file.uploaded", project_file_event_payload(project_file))
    return project_file


def calculate_risk_score(file_name, size_bytes):
    extension = infer_extension(file_name).lower()
    score = 5
    if size_bytes >= 1024 * 1024 * 1024:
        score += 20
    if extension in {"exe", "dll", "bat", "cmd", "ps1", "sh"}:
        score += 60
    if extension in {"env", "conf", "sql"}:
        score += 20
    return min(100, score)


def project_file_event_payload(project_file):
    return {
        "id": str(project_file.id),
        "name": project_file.original_name,
        "status": project_file.status,
        "size_bytes": project_file.size_bytes,
        "uploaded_by": project_file.uploaded_by_id,
        "destination_device": project_file.destination_device_id,
    }


def deploy_project_file(project_file, destination_device, user=None, approved_by=None, destination_relative_path=""):
    source = Path(project_file.storage_path)
    if not source.exists():
        project_file.status = ProjectFile.Status.FAILED
        project_file.save(update_fields=["status", "updated_at"])
        raise FileNotFoundError("Uploaded source file is missing.")
    destination_root = safe_storage_path(destination_device.storage_path, destination_device.device_id)
    destination_dir = safe_child_path(destination_root, destination_relative_path or "")
    destination = unique_destination_path(destination_dir, project_file.original_name)
    job = DesktopTransferJob.objects.create(
        source_device=project_file.source_device,
        destination_device=destination_device,
        project_file=project_file,
        file_name=project_file.original_name,
        source_path=str(source),
        destination_path=str(destination),
        size_bytes=project_file.size_bytes,
        status=DesktopTransferJob.Status.IN_PROGRESS,
        transfer_mode="chunked-copy",
        encryption="TLS 1.3 + SHA-256 verification",
        checksum=project_file.checksum,
        started_at=timezone.now(),
        uploaded_by=project_file.uploaded_by,
        approved_by=approved_by if getattr(approved_by, "is_authenticated", False) else user if getattr(user, "is_authenticated", False) else None,
    )
    project_file.status = ProjectFile.Status.DEPLOYING
    project_file.approved_by = job.approved_by or project_file.approved_by
    project_file.approved_at = project_file.approved_at or timezone.now()
    project_file.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    write_audit("transfer_started", f"Deploying {project_file.original_name} to {destination_device.name}", actor=user, device=destination_device, project_file=project_file, transfer_job=job)
    broadcast_desktop_event("transfer.started", transfer_event_payload(job))
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        start = time.monotonic()
        transferred = 0
        chunk_size = 4 * 1024 * 1024
        with open(source, "rb") as input_file, open(destination, "wb") as output_file:
            for chunk in iter(lambda: input_file.read(chunk_size), b""):
                output_file.write(chunk)
                transferred += len(chunk)
                elapsed = max(time.monotonic() - start, 0.001)
                job.bytes_transferred = transferred
                job.progress_percent = round((transferred / max(project_file.size_bytes, 1)) * 100, 2)
                job.speed_bytes_per_sec = transferred / elapsed
                job.save(update_fields=["bytes_transferred", "progress_percent", "speed_bytes_per_sec", "updated_at"])
                broadcast_desktop_event("transfer.progress", transfer_event_payload(job))
        checksum = hash_file(destination)
        if project_file.checksum and checksum != project_file.checksum:
            raise ValueError("Checksum validation failed after transfer.")
        job.status = DesktopTransferJob.Status.COMPLETED
        job.progress_percent = 100
        job.bytes_transferred = project_file.size_bytes
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "progress_percent", "bytes_transferred", "completed_at", "updated_at"])
        project_file.status = ProjectFile.Status.DEPLOYED
        project_file.deployed_at = timezone.now()
        project_file.deployed_path = str(destination)
        project_file.destination_device = destination_device
        project_file.save(update_fields=["status", "deployed_at", "deployed_path", "destination_device", "updated_at"])
        storage_file, _ = PhysicalStorageFile.objects.update_or_create(
            path=str(destination),
            defaults={
                "device": destination_device,
                "name": destination.name,
                "extension": infer_extension(destination.name),
                "size_bytes": destination.stat().st_size,
                "checksum": checksum,
                "owner": project_file.uploaded_by,
                "uploaded_at": timezone.now(),
                "metadata": {"project_file_id": str(project_file.id), "transfer_job_id": str(job.id)},
            },
        )
        record_transfer(
            {
                "file_name": project_file.original_name,
                "source_path": str(source),
                "destination_path": str(destination),
                "source_label": project_file.source_device.name if project_file.source_device else "upload",
                "destination_label": destination_device.name,
                "source_disk_type": DiskVolume.DiskType.NETWORK,
                "destination_disk_type": DiskVolume.DiskType.NETWORK,
                "size_bytes": project_file.size_bytes,
                "checksum": checksum,
                "status": FileTransfer.Status.COMPLETED,
                "process_name": "desktop-transfer-engine",
                "metadata": {"desktop_transfer_job_id": str(job.id), "storage_file_id": str(storage_file.id)},
            },
            user=project_file.uploaded_by,
        )
        write_audit("transfer_completed", f"{project_file.original_name} deployed to {destination}", actor=user, device=destination_device, project_file=project_file, transfer_job=job)
        broadcast_desktop_event("transfer.completed", transfer_event_payload(job))
        return job
    except Exception as exc:
        job.status = DesktopTransferJob.Status.FAILED
        job.last_error = str(exc)
        job.save(update_fields=["status", "last_error", "updated_at"])
        project_file.status = ProjectFile.Status.FAILED
        project_file.save(update_fields=["status", "updated_at"])
        write_audit("transfer_failed", str(exc), actor=user, device=destination_device, project_file=project_file, transfer_job=job)
        broadcast_desktop_event("transfer.failed", transfer_event_payload(job))
        raise


def transfer_event_payload(job):
    return {
        "id": str(job.id),
        "file_name": job.file_name,
        "status": job.status,
        "progress_percent": job.progress_percent,
        "bytes_transferred": job.bytes_transferred,
        "size_bytes": job.size_bytes,
        "speed_bytes_per_sec": job.speed_bytes_per_sec,
        "source_device": job.source_device_id,
        "destination_device": job.destination_device_id,
        "last_error": job.last_error,
    }


def sync_storage_index(device=None):
    ensure_transfer_directories()
    devices = [device] if device else list(DesktopDevice.objects.filter(is_deleted=False, device_type__in=[DesktopDevice.DeviceType.SERVER, DesktopDevice.DeviceType.NAS, DesktopDevice.DeviceType.STORAGE]))
    if not devices:
        default_device, _ = DesktopDevice.objects.get_or_create(
            device_id="PHYSICAL-SERVER-DEFAULT",
            defaults={
                "name": "Physical Server Storage",
                "device_type": DesktopDevice.DeviceType.SERVER,
                "status": DesktopDevice.Status.ONLINE,
                "storage_path": str(settings.DESKTOP_TRANSFER_SERVER_ROOT),
                "transfer_status": "ready",
            },
        )
        devices = [default_device]
    indexed = []
    for current in devices:
        root = safe_storage_path(current.storage_path, current.device_id)
        root.mkdir(parents=True, exist_ok=True)
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            storage_file, _ = PhysicalStorageFile.objects.update_or_create(
                path=str(path),
                defaults={
                    "device": current,
                    "name": path.name,
                    "extension": infer_extension(path.name),
                    "size_bytes": path.stat().st_size,
                    "checksum": hash_file(path),
                    "uploaded_at": timezone.datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.get_current_timezone()),
                },
            )
            indexed.append(storage_file)
    return indexed


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

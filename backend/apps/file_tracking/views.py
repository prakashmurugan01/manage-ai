import csv
from io import StringIO
from pathlib import Path

from django.db.models import Sum
from django.http import FileResponse
from django.http import HttpResponse
from django.utils.text import get_valid_filename
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.views import APIView

from apps.core.views import api_response
from apps.file_tracking.models import (
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
from apps.file_tracking.serializers import (
    ChunkUploadSessionSerializer,
    DesktopDeviceSerializer,
    DesktopTransferAuditLogSerializer,
    DesktopTransferJobSerializer,
    DeviceConnectionSerializer,
    DiskVolumeSerializer,
    FileAlertSerializer,
    FileEventSerializer,
    FileTransferCreateSerializer,
    FileTransferSerializer,
    PhysicalStorageFileSerializer,
    ProjectFileSerializer,
    TrackingRuleSerializer,
)
from apps.file_tracking.services import (
    broadcast_desktop_event,
    dashboard_summary,
    deploy_project_file,
    handle_chunk_upload,
    hash_file,
    record_transfer,
    register_device,
    safe_child_path,
    safe_storage_path,
    set_connection_status,
    sync_storage_index,
    write_audit,
)
from apps.modules.api import BaseModuleViewSet


def is_admin_role(user):
    return bool(
        getattr(user, "is_superuser", False)
        or getattr(user, "is_staff", False)
        or getattr(user, "role", "") in {"SUPER_ADMIN", "ADMIN"}
    )


class AdminRolePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and is_admin_role(request.user)


class DiskTrackingDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return api_response(dashboard_summary())


class DiskVolumeViewSet(BaseModuleViewSet):
    queryset = DiskVolume.objects.all()
    serializer_class = DiskVolumeSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["label", "mount_path", "disk_type"]
    ordering_fields = ["label", "used_bytes", "free_bytes", "last_seen_at", "created_at"]


class FileTransferViewSet(BaseModuleViewSet):
    queryset = FileTransfer.objects.select_related("source_volume", "destination_volume", "initiated_by")
    serializer_class = FileTransferSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["file_name", "source_path", "destination_path", "checksum", "process_name"]
    ordering_fields = ["created_at", "size_bytes", "completed_at", "risk_score"]

    def create(self, request, *args, **kwargs):
        serializer = FileTransferCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        transfer = record_transfer(serializer.validated_data, request.user)
        return api_response(FileTransferSerializer(transfer).data, http_status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def export(self, request):
        fmt = request.query_params.get("format", "csv")
        queryset = self.filter_queryset(self.get_queryset())
        if fmt == "json":
            return api_response(FileTransferSerializer(queryset[:1000], many=True).data)
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["file_name", "size_bytes", "source_path", "destination_path", "status", "risk_score", "created_at"])
        for transfer in queryset[:10000]:
            writer.writerow([transfer.file_name, transfer.size_bytes, transfer.source_path, transfer.destination_path, transfer.status, transfer.risk_score, transfer.created_at.isoformat()])
        response = HttpResponse(buffer.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="file-transfers.csv"'
        return response


class FileEventViewSet(BaseModuleViewSet):
    queryset = FileEvent.objects.select_related("transfer")
    serializer_class = FileEventSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["event_type", "source_path", "destination_path"]
    ordering_fields = ["observed_at", "created_at"]


class FileAlertViewSet(BaseModuleViewSet):
    queryset = FileAlert.objects.select_related("transfer", "rule", "acknowledged_by")
    serializer_class = FileAlertSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["message", "severity", "status", "transfer__file_name"]
    ordering_fields = ["severity", "status", "created_at"]

    @action(detail=True, methods=["post"])
    def acknowledge(self, request, pk=None):
        alert = self.get_object()
        alert.status = FileAlert.Status.ACKNOWLEDGED
        alert.acknowledged_by = request.user
        alert.acknowledged_at = timezone.now()
        alert.save(update_fields=["status", "acknowledged_by", "acknowledged_at", "updated_at"])
        return api_response(FileAlertSerializer(alert).data)

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        alert = self.get_object()
        alert.status = FileAlert.Status.RESOLVED
        alert.resolved_at = timezone.now()
        alert.save(update_fields=["status", "resolved_at", "updated_at"])
        return api_response(FileAlertSerializer(alert).data)


class TrackingRuleViewSet(BaseModuleViewSet):
    queryset = TrackingRule.objects.all()
    serializer_class = TrackingRuleSerializer
    permission_classes = [permissions.IsAdminUser]
    search_fields = ["name", "rule_type", "severity"]
    ordering_fields = ["name", "rule_type", "created_at"]


class DesktopTransferSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        devices = DesktopDevice.objects.filter(is_deleted=False)
        files = ProjectFile.objects.filter(is_deleted=False)
        jobs = DesktopTransferJob.objects.filter(is_deleted=False)
        if not is_admin_role(request.user):
            files = files.filter(uploaded_by=request.user)
            jobs = jobs.filter(uploaded_by=request.user)
        return api_response(
            {
                "devices": {
                    "total": devices.count(),
                    "online": devices.filter(status=DesktopDevice.Status.ONLINE).count(),
                    "offline": devices.filter(status=DesktopDevice.Status.OFFLINE).count(),
                },
                "files": {
                    "pending": files.filter(status=ProjectFile.Status.PENDING).count(),
                    "approved": files.filter(status=ProjectFile.Status.APPROVED).count(),
                    "deployed": files.filter(status=ProjectFile.Status.DEPLOYED).count(),
                    "rejected": files.filter(status=ProjectFile.Status.REJECTED).count(),
                },
                "transfers": {
                    "active": jobs.filter(status=DesktopTransferJob.Status.IN_PROGRESS).count(),
                    "completed": jobs.filter(status=DesktopTransferJob.Status.COMPLETED).count(),
                    "failed": jobs.filter(status=DesktopTransferJob.Status.FAILED).count(),
                    "bytes_moved": jobs.filter(status=DesktopTransferJob.Status.COMPLETED).aggregate(total=Sum("size_bytes"))["total"] or 0,
                },
                "storage": {
                    "files": PhysicalStorageFile.objects.filter(is_deleted=False).count(),
                    "bytes": PhysicalStorageFile.objects.filter(is_deleted=False).aggregate(total=Sum("size_bytes"))["total"] or 0,
                },
            }
        )


class DesktopDeviceViewSet(BaseModuleViewSet):
    queryset = DesktopDevice.objects.select_related("owner")
    serializer_class = DesktopDeviceSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["device_id", "name", "ip_address", "mac_address", "os_name", "storage_path"]
    ordering_fields = ["name", "status", "last_seen_at", "created_at"]

    def create(self, request, *args, **kwargs):
        try:
            device = register_device(request.data, request.user)
        except ValueError as exc:
            return api_response(errors=[str(exc)], http_status=status.HTTP_400_BAD_REQUEST)
        return api_response(DesktopDeviceSerializer(device).data, http_status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def heartbeat(self, request, pk=None):
        device = self.get_object()
        for key in ["cpu_percent", "ram_percent", "disk_percent", "used_storage_bytes", "total_storage_bytes", "transfer_status"]:
            if key in request.data:
                setattr(device, key, request.data[key])
        device.status = DesktopDevice.Status.ONLINE
        device.last_seen_at = timezone.now()
        device.save()
        broadcast_desktop_event("device.heartbeat", {"id": str(device.id), "status": device.status, "last_seen_at": device.last_seen_at.isoformat()})
        return api_response(DesktopDeviceSerializer(device).data)

    @action(detail=True, methods=["post"], permission_classes=[AdminRolePermission])
    def mark_offline(self, request, pk=None):
        device = self.get_object()
        device.status = DesktopDevice.Status.OFFLINE
        device.save(update_fields=["status", "updated_at"])
        write_audit("device_offline", f"{device.name} marked offline", actor=request.user, device=device)
        broadcast_desktop_event("device.updated", {"id": str(device.id), "status": device.status})
        return api_response(DesktopDeviceSerializer(device).data)


class DeviceConnectionViewSet(BaseModuleViewSet):
    queryset = DeviceConnection.objects.select_related("source_device", "destination_device", "connected_by")
    serializer_class = DeviceConnectionSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["source_device__name", "destination_device__name", "status", "transport"]
    ordering_fields = ["status", "connected_at", "updated_at"]

    def create(self, request, *args, **kwargs):
        source = DesktopDevice.objects.get(id=request.data.get("source_device"))
        destination = DesktopDevice.objects.get(id=request.data.get("destination_device"))
        connection, _ = DeviceConnection.objects.get_or_create(
            source_device=source,
            destination_device=destination,
            defaults={
                "transport": request.data.get("transport", "webrtc"),
                "encryption": request.data.get("encryption", "TLS 1.3"),
                "connected_by": request.user,
            },
        )
        connection.transport = request.data.get("transport", connection.transport)
        connection.encryption = request.data.get("encryption", connection.encryption)
        connection.save(update_fields=["transport", "encryption", "updated_at"])
        set_connection_status(connection, DeviceConnection.Status.CONNECTED, request.user)
        return api_response(DeviceConnectionSerializer(connection).data, http_status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def connect(self, request, pk=None):
        connection = self.get_object()
        set_connection_status(connection, DeviceConnection.Status.CONNECTED, request.user)
        return api_response(DeviceConnectionSerializer(connection).data)

    @action(detail=True, methods=["post"])
    def disconnect(self, request, pk=None):
        connection = self.get_object()
        set_connection_status(connection, DeviceConnection.Status.DISCONNECTED, request.user)
        return api_response(DeviceConnectionSerializer(connection).data)


class ChunkUploadView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        chunk = request.FILES.get("chunk") or request.FILES.get("file")
        if not chunk:
            return api_response(errors=["Missing chunk file."], http_status=status.HTTP_400_BAD_REQUEST)
        try:
            session, project_file = handle_chunk_upload(request.data, chunk, request.user)
        except Exception as exc:
            return api_response(errors=[str(exc)], http_status=status.HTTP_400_BAD_REQUEST)
        return api_response(
            {
                "session": ChunkUploadSessionSerializer(session).data,
                "file": ProjectFileSerializer(project_file).data if project_file else None,
            },
            http_status=status.HTTP_201_CREATED if project_file else status.HTTP_202_ACCEPTED,
        )


class ProjectFileViewSet(BaseModuleViewSet):
    queryset = ProjectFile.objects.select_related("uploaded_by", "approved_by", "source_device", "destination_device")
    serializer_class = ProjectFileSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["original_name", "relative_path", "extension", "status", "uploaded_by__email", "source_device__name", "destination_device__name"]
    ordering_fields = ["created_at", "size_bytes", "status", "risk_score", "deployed_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if not is_admin_role(self.request.user):
            queryset = queryset.filter(uploaded_by=self.request.user)
        return queryset

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        project_file = self.get_object()
        path = Path(project_file.storage_path)
        if not path.exists():
            return api_response(errors=["File is missing from upload storage."], http_status=status.HTTP_404_NOT_FOUND)
        write_audit("file_downloaded", f"{project_file.original_name} downloaded", actor=request.user, project_file=project_file)
        return FileResponse(open(path, "rb"), as_attachment=True, filename=project_file.original_name)

    @action(detail=True, methods=["get"])
    def preview(self, request, pk=None):
        project_file = self.get_object()
        path = Path(project_file.storage_path)
        if not path.exists():
            return api_response(errors=["File is missing from upload storage."], http_status=status.HTTP_404_NOT_FOUND)
        return FileResponse(open(path, "rb"), as_attachment=False, filename=project_file.original_name)

    @action(detail=True, methods=["post"], permission_classes=[AdminRolePermission])
    def approve(self, request, pk=None):
        project_file = self.get_object()
        destination = None
        if request.data.get("destination_device"):
            destination = DesktopDevice.objects.filter(id=request.data.get("destination_device")).first()
        destination = destination or project_file.destination_device or DesktopDevice.objects.filter(device_type=DesktopDevice.DeviceType.SERVER, is_deleted=False).first()
        if not destination:
            destination = register_device(
                {"device_id": "PHYSICAL-SERVER-DEFAULT", "name": "Physical Server Storage", "device_type": DesktopDevice.DeviceType.SERVER, "storage_path": "/server_storage/projects/"},
                request.user,
            )
        project_file.status = ProjectFile.Status.APPROVED
        project_file.approved_by = request.user
        project_file.approved_at = timezone.now()
        project_file.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        broadcast_desktop_event("project_file.approved", {"id": str(project_file.id), "status": project_file.status})
        try:
            job = deploy_project_file(project_file, destination, request.user, approved_by=request.user, destination_relative_path=request.data.get("destination_path", ""))
        except Exception as exc:
            return api_response(errors=[str(exc)], http_status=status.HTTP_400_BAD_REQUEST)
        return api_response({"file": ProjectFileSerializer(project_file).data, "transfer": DesktopTransferJobSerializer(job).data})

    @action(detail=True, methods=["post"], permission_classes=[AdminRolePermission])
    def reject(self, request, pk=None):
        project_file = self.get_object()
        project_file.status = ProjectFile.Status.REJECTED
        project_file.rejected_by = request.user
        project_file.rejected_at = timezone.now()
        project_file.rejection_reason = request.data.get("reason", "")
        project_file.save(update_fields=["status", "rejected_by", "rejected_at", "rejection_reason", "updated_at"])
        write_audit("file_rejected", f"{project_file.original_name} rejected", actor=request.user, project_file=project_file, metadata={"reason": project_file.rejection_reason})
        broadcast_desktop_event("project_file.rejected", {"id": str(project_file.id), "reason": project_file.rejection_reason})
        return api_response(ProjectFileSerializer(project_file).data)

    @action(detail=True, methods=["post"], permission_classes=[AdminRolePermission])
    def deploy(self, request, pk=None):
        project_file = self.get_object()
        destination = DesktopDevice.objects.filter(id=request.data.get("destination_device")).first() or project_file.destination_device
        if not destination:
            return api_response(errors=["Destination device is required."], http_status=status.HTTP_400_BAD_REQUEST)
        try:
            job = deploy_project_file(project_file, destination, request.user, approved_by=request.user, destination_relative_path=request.data.get("destination_path", ""))
        except Exception as exc:
            return api_response(errors=[str(exc)], http_status=status.HTTP_400_BAD_REQUEST)
        return api_response(DesktopTransferJobSerializer(job).data)


class DesktopTransferJobViewSet(BaseModuleViewSet):
    queryset = DesktopTransferJob.objects.select_related("source_device", "destination_device", "project_file", "uploaded_by", "approved_by")
    serializer_class = DesktopTransferJobSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["file_name", "source_path", "destination_path", "status", "source_device__name", "destination_device__name"]
    ordering_fields = ["created_at", "size_bytes", "progress_percent", "status", "completed_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if not is_admin_role(self.request.user):
            queryset = queryset.filter(uploaded_by=self.request.user)
        return queryset

    def create(self, request, *args, **kwargs):
        destination = DesktopDevice.objects.filter(id=request.data.get("destination_device")).first()
        if not destination:
            return api_response(errors=["Destination device is required."], http_status=status.HTTP_400_BAD_REQUEST)
        project_file = ProjectFile.objects.filter(id=request.data.get("project_file")).first()
        if not project_file:
            source = DesktopDevice.objects.filter(id=request.data.get("source_device")).first()
            if not source:
                return api_response(errors=["Source device or project file is required."], http_status=status.HTTP_400_BAD_REQUEST)
            source_root = safe_storage_path(source.storage_path, source.device_id)
            source_path = safe_child_path(source_root, request.data.get("source_path", ""))
            if not source_path.exists() or not source_path.is_file():
                return api_response(errors=["Source file does not exist on the source device storage path."], http_status=status.HTTP_404_NOT_FOUND)
            project_file = ProjectFile.objects.create(
                original_name=source_path.name,
                stored_name=source_path.name,
                storage_path=str(source_path),
                content_type="application/octet-stream",
                extension=source_path.suffix.lstrip(".").lower(),
                size_bytes=source_path.stat().st_size,
                checksum=hash_file(source_path),
                status=ProjectFile.Status.APPROVED,
                source_device=source,
                destination_device=destination,
                uploaded_by=request.user,
                approved_by=request.user if is_admin_role(request.user) else None,
                approved_at=timezone.now() if is_admin_role(request.user) else None,
            )
        if not is_admin_role(request.user) and project_file.uploaded_by_id != request.user.id:
            return api_response(errors=["You cannot transfer another user's file."], http_status=status.HTTP_403_FORBIDDEN)
        try:
            job = deploy_project_file(project_file, destination, request.user, approved_by=request.user if is_admin_role(request.user) else project_file.approved_by)
        except Exception as exc:
            return api_response(errors=[str(exc)], http_status=status.HTTP_400_BAD_REQUEST)
        return api_response(DesktopTransferJobSerializer(job).data, http_status=status.HTTP_201_CREATED)


class PhysicalStorageFileViewSet(BaseModuleViewSet):
    queryset = PhysicalStorageFile.objects.select_related("device", "owner")
    serializer_class = PhysicalStorageFileSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["name", "path", "extension", "owner__email", "device__name"]
    ordering_fields = ["name", "size_bytes", "uploaded_at", "created_at"]

    def list(self, request, *args, **kwargs):
        sync_storage_index()
        return super().list(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        storage_file = self.get_object()
        path = Path(storage_file.path)
        if not path.exists():
            return api_response(errors=["Storage file is missing."], http_status=status.HTTP_404_NOT_FOUND)
        write_audit("storage_downloaded", f"{storage_file.name} downloaded", actor=request.user, device=storage_file.device)
        return FileResponse(open(path, "rb"), as_attachment=True, filename=storage_file.name)

    @action(detail=True, methods=["delete"], permission_classes=[AdminRolePermission])
    def delete_file(self, request, pk=None):
        storage_file = self.get_object()
        path = Path(storage_file.path)
        if path.exists():
            path.unlink()
        storage_file.is_deleted = True
        storage_file.save(update_fields=["is_deleted", "updated_at"])
        write_audit("storage_deleted", f"{storage_file.name} deleted", actor=request.user, device=storage_file.device)
        broadcast_desktop_event("storage.deleted", {"id": str(storage_file.id)})
        return api_response({})

    @action(detail=True, methods=["post"], permission_classes=[AdminRolePermission])
    def rename(self, request, pk=None):
        storage_file = self.get_object()
        path = Path(storage_file.path)
        if not path.exists():
            return api_response(errors=["Storage file is missing."], http_status=status.HTTP_404_NOT_FOUND)
        new_name = get_valid_filename(request.data.get("name") or "")
        if not new_name:
            return api_response(errors=["New name is required."], http_status=status.HTTP_400_BAD_REQUEST)
        next_path = path.with_name(new_name)
        path.rename(next_path)
        storage_file.name = next_path.name
        storage_file.path = str(next_path)
        storage_file.extension = next_path.suffix.lstrip(".").lower()
        storage_file.save(update_fields=["name", "path", "extension", "updated_at"])
        write_audit("storage_renamed", f"{path.name} renamed to {next_path.name}", actor=request.user, device=storage_file.device)
        broadcast_desktop_event("storage.renamed", {"id": str(storage_file.id), "name": storage_file.name})
        return api_response(PhysicalStorageFileSerializer(storage_file).data)

    @action(detail=True, methods=["post"], permission_classes=[AdminRolePermission])
    def move(self, request, pk=None):
        storage_file = self.get_object()
        path = Path(storage_file.path)
        if not path.exists():
            return api_response(errors=["Storage file is missing."], http_status=status.HTTP_404_NOT_FOUND)
        root = safe_storage_path(storage_file.device.storage_path if storage_file.device else None, storage_file.device.device_id if storage_file.device else "default")
        target_dir = safe_child_path(root, request.data.get("folder", ""))
        target_dir.mkdir(parents=True, exist_ok=True)
        next_path = target_dir / path.name
        path.rename(next_path)
        storage_file.path = str(next_path)
        storage_file.save(update_fields=["path", "updated_at"])
        write_audit("storage_moved", f"{storage_file.name} moved", actor=request.user, device=storage_file.device, metadata={"folder": request.data.get("folder", "")})
        broadcast_desktop_event("storage.moved", {"id": str(storage_file.id), "path": storage_file.path})
        return api_response(PhysicalStorageFileSerializer(storage_file).data)


class DesktopTransferAuditLogViewSet(BaseModuleViewSet):
    queryset = DesktopTransferAuditLog.objects.select_related("actor", "device", "project_file", "transfer_job")
    serializer_class = DesktopTransferAuditLogSerializer
    permission_classes = [AdminRolePermission]
    search_fields = ["action", "message", "actor__email"]
    ordering_fields = ["created_at", "action"]

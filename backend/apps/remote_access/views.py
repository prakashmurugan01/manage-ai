import math
import mimetypes
import os
import shutil
import uuid
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.http import FileResponse, Http404, StreamingHttpResponse
from django.utils import timezone
from django.utils.text import get_valid_filename
from urllib.parse import parse_qs, urlparse
from rest_framework import decorators, status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import Roles, has_role, is_admin_level

from .models import RemoteActivityLog, RemoteDevice, RemoteSession, RemoteTransfer
from .serializers import RemoteActivityLogSerializer, RemoteDeviceSerializer, RemoteSessionSerializer, RemoteTransferSerializer


def log_action(action, message, actor=None, device=None, session=None, metadata=None):
    return RemoteActivityLog.objects.create(action=action, message=message, actor=actor, device=device, session=session, metadata=metadata or {})


def send_to_device(device_id, event):
    async_to_sync(get_channel_layer().group_send)(f"remote_device_{device_id}", {"type": "device.message", "event": event})


def broadcast_transfer(session, transfer):
    payload = {"type": "transfer.progress", "session_token": session.token, "transfer": RemoteTransferSerializer(transfer).data}
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(f"remote_session_{session.token}", {"type": "session.message", "event": payload})
    async_to_sync(channel_layer.group_send)("remote_access_dashboard", {"type": "dashboard.message", "event": payload})


def normalize_connection_token(value):
    token = (value or "").strip()
    if not token:
        return ""
    parsed = urlparse(token)
    if parsed.query:
        query = parse_qs(parsed.query)
        token = (query.get("token") or query.get("connection") or [token])[0]
    return token.strip()


class RemoteDeviceViewSet(viewsets.ModelViewSet):
    serializer_class = RemoteDeviceSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status", "platform"]
    search_fields = ["name", "hostname", "fingerprint"]
    ordering_fields = ["name", "status", "last_seen_at", "created_at"]
    ordering = ["-last_seen_at"]

    def get_queryset(self):
        qs = RemoteDevice.objects.all()
        if is_admin_level(self.request.user):
            return qs
        return (qs.filter(owner=self.request.user) | qs.filter(sessions__requested_by=self.request.user)).distinct()

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @decorators.action(detail=False, methods=["get"])
    def dashboard(self, request):
        devices = self.get_queryset()
        sessions_qs = RemoteSession.objects.filter(device__in=devices)
        if not is_admin_level(request.user):
            sessions_qs = sessions_qs | RemoteSession.objects.filter(requested_by=request.user)
        sessions_qs = sessions_qs.select_related("device", "requested_by").distinct()
        active_sessions = sessions_qs.filter(status=RemoteSession.Status.ACTIVE).count()
        sessions = list(sessions_qs[:12])
        session_ids = [session.id for session in sessions]
        logs = (
            RemoteActivityLog.objects.filter(device__in=devices)
            | RemoteActivityLog.objects.filter(session_id__in=session_ids)
        ).select_related("device", "session", "actor").distinct()[:20]
        return Response(
            {
                "summary": {
                    "devices": devices.count(),
                    "online": devices.filter(status=RemoteDevice.Status.ONLINE).count(),
                    "active_sessions": active_sessions,
                    "transfers": RemoteTransfer.objects.filter(session__device__in=devices).count(),
                },
                "devices": RemoteDeviceSerializer(devices[:30], many=True).data,
                "sessions": RemoteSessionSerializer(sessions, many=True).data,
                "logs": RemoteActivityLogSerializer(logs, many=True).data,
            }
        )

    @decorators.action(detail=False, methods=["post"], url_path="connect-token")
    def connect_token(self, request):
        token = normalize_connection_token(request.data.get("token"))
        if not token:
            raise ValidationError({"token": "Connection token is required."})
        device = RemoteDevice.objects.filter(token=token).first()
        if not device:
            raise ValidationError({"token": "No remote device is available for this token."})
        permission = request.data.get("permission", RemoteSession.Permission.VIEW)
        return self._create_session_request(device, request, permission)

    @decorators.action(detail=True, methods=["post"], url_path="request-session")
    def request_session(self, request, pk=None):
        device = self.get_object()
        permission = request.data.get("permission", RemoteSession.Permission.VIEW)
        return self._create_session_request(device, request, permission)

    def _create_session_request(self, device, request, permission):
        if permission not in RemoteSession.Permission.values:
            raise ValidationError({"permission": "Invalid permission."})
        if permission in {RemoteSession.Permission.CONTROL, RemoteSession.Permission.ADMIN} and not is_admin_level(request.user):
            raise PermissionDenied("Full control requires Admin or Super Admin permission.")
        if device.status == RemoteDevice.Status.OFFLINE:
            return Response(
                {
                    "message": "The target agent is offline. Start the desktop agent before connecting.",
                    "code": "agent_offline",
                    "device": RemoteDeviceSerializer(device).data,
                },
                status=status.HTTP_409_CONFLICT,
            )
        session = RemoteSession.objects.create(device=device, requested_by=request.user, permission=permission, offer=request.data.get("offer") or {})
        device.status = RemoteDevice.Status.PENDING
        device.save(update_fields=["status", "updated_at"])
        log_action(RemoteActivityLog.Action.SESSION_REQUEST, f"{request.user.email} requested {permission.lower()} access.", request.user, device, session)
        send_to_device(device.id, {"type": "session.request", "session": RemoteSessionSerializer(session).data})
        return Response(RemoteSessionSerializer(session).data, status=status.HTTP_201_CREATED)


class RemoteSessionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RemoteSessionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status", "permission", "device"]
    ordering_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = RemoteSession.objects.select_related("device", "requested_by")
        if is_admin_level(self.request.user):
            return qs
        return qs.filter(requested_by=self.request.user)

    def _assert_can_operate(self, session):
        if session.requested_by_id == self.request.user.id or is_admin_level(self.request.user):
            return
        raise PermissionDenied("You do not have access to this remote session.")

    @decorators.action(detail=True, methods=["post"])
    def disconnect(self, request, pk=None):
        session = self.get_object()
        self._assert_can_operate(session)
        session.status = RemoteSession.Status.ENDED
        session.ended_at = timezone.now()
        session.save(update_fields=["status", "ended_at", "updated_at"])
        session.device.status = RemoteDevice.Status.ONLINE
        session.device.save(update_fields=["status", "updated_at"])
        log_action(RemoteActivityLog.Action.SESSION_ENDED, "Remote session disconnected.", request.user, session.device, session)
        send_to_device(session.device_id, {"type": "session.disconnect", "session_token": session.token})
        return Response(RemoteSessionSerializer(session).data)

    @decorators.action(detail=True, methods=["post"], url_path="command")
    def command(self, request, pk=None):
        session = self.get_object()
        self._assert_can_operate(session)
        if session.status not in {RemoteSession.Status.APPROVED, RemoteSession.Status.ACTIVE}:
            raise ValidationError("Session must be approved before commands can be sent.")
        command = request.data.get("command")
        payload = request.data.get("payload", {})
        if command in {"mouse", "keyboard"} and session.permission not in {RemoteSession.Permission.CONTROL, RemoteSession.Permission.ADMIN}:
            raise PermissionDenied("This session is view-only.")
        log_action(RemoteActivityLog.Action.CONTROL, f"Sent {command} command.", request.user, session.device, session, {"command": command})
        send_to_device(session.device_id, {"type": "session.command", "session_token": session.token, "command": command, "payload": payload})
        return Response({"queued": True})

    @decorators.action(detail=True, methods=["post"], url_path="files")
    def files(self, request, pk=None):
        session = self.get_object()
        self._assert_can_operate(session)
        if session.permission not in {RemoteSession.Permission.FILES, RemoteSession.Permission.ADMIN}:
            raise PermissionDenied("File access is not enabled for this session.")
        action = request.data.get("action", "list")
        payload = request.data.get("payload", {})
        if action == "delete" and not has_role(request.user, Roles.SUPER_ADMIN):
            raise PermissionDenied("Delete requires Super Admin permission.")
        log_action(RemoteActivityLog.Action.FILE_BROWSE if action == "list" else RemoteActivityLog.Action.FILE_DELETE, f"File action requested: {action}.", request.user, session.device, session, payload)
        send_to_device(session.device_id, {"type": "file.command", "session_token": session.token, "action": action, "payload": payload})
        return Response({"queued": True})


class RemoteTransferViewSet(viewsets.ModelViewSet):
    serializer_class = RemoteTransferSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status", "direction", "session"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = RemoteTransfer.objects.select_related("session", "session__device")
        if is_admin_level(self.request.user):
            return qs
        return qs.filter(created_by=self.request.user)

    def perform_create(self, serializer):
        session = serializer.validated_data["session"]
        if session.permission not in {RemoteSession.Permission.FILES, RemoteSession.Permission.ADMIN}:
            raise PermissionDenied("File transfers require file access.")
        transfer = serializer.save(created_by=self.request.user)
        log_action(RemoteActivityLog.Action.FILE_DOWNLOAD, "Queued file transfer.", self.request.user, session.device, session, {"transfer_id": transfer.id})
        send_to_device(session.device_id, {"type": "file.transfer", "session_token": session.token, "transfer": RemoteTransferSerializer(transfer).data})

    def _assert_session_transfer_access(self, session):
        if session.permission not in {RemoteSession.Permission.FILES, RemoteSession.Permission.ADMIN}:
            raise PermissionDenied("File transfers require file access.")
        if session.requested_by_id == self.request.user.id or is_admin_level(self.request.user):
            return
        raise PermissionDenied("You do not have access to this remote session.")

    def _assert_transfer_access(self, transfer):
        self._assert_session_transfer_access(transfer.session)
        return transfer

    def _transfer_root(self, *parts):
        root = os.path.abspath(settings.MEDIA_ROOT / "remote_transfers")
        path = os.path.abspath(os.path.join(root, *[str(part) for part in parts]))
        if path != root and not path.startswith(root + os.sep):
            raise ValidationError("Invalid transfer path.")
        os.makedirs(os.path.dirname(path) if os.path.splitext(path)[1] else path, exist_ok=True)
        return path

    def _safe_filename(self, name):
        cleaned = get_valid_filename(os.path.basename(name or "upload.bin")) or "upload.bin"
        stem, ext = os.path.splitext(cleaned)
        return f"{stem[:120] or 'upload'}-{uuid.uuid4().hex[:12]}{ext[:20]}"

    def _validate_upload(self, original_name, size_bytes, content_type):
        max_bytes = int(getattr(settings, "DATA_UPLOAD_MAX_MEMORY_SIZE", 5 * 1024 * 1024 * 1024))
        if size_bytes <= 0:
            raise ValidationError({"size_bytes": "File size must be greater than zero."})
        if size_bytes > max_bytes:
            raise ValidationError({"size_bytes": f"File is larger than the {max_bytes} byte transfer limit."})
        blocked_exts = {".exe", ".dll", ".bat", ".cmd", ".ps1", ".msi", ".scr", ".vbs", ".js"}
        ext = os.path.splitext(original_name or "")[1].lower()
        if ext in blocked_exts:
            raise ValidationError({"name": "This executable file type is blocked for browser uploads."})
        blocked_types = {"application/x-msdownload", "application/x-msdos-program"}
        if content_type in blocked_types:
            raise ValidationError({"content_type": "This file type is blocked for browser uploads."})

    @decorators.action(detail=False, methods=["post"], url_path="uploads/initiate")
    def initiate_upload(self, request):
        session = RemoteSession.objects.filter(id=request.data.get("session")).select_related("device", "requested_by").first()
        if not session:
            raise ValidationError({"session": "A valid remote session is required."})
        self._assert_session_transfer_access(session)
        original_name = request.data.get("name") or "upload.bin"
        size_bytes = int(request.data.get("size_bytes") or 0)
        content_type = request.data.get("content_type") or mimetypes.guess_type(original_name)[0] or "application/octet-stream"
        chunk_size = max(1024 * 1024, min(int(request.data.get("chunk_size") or 1024 * 1024), 5 * 1024 * 1024))
        self._validate_upload(original_name, size_bytes, content_type)
        stored_name = self._safe_filename(original_name)
        transfer = RemoteTransfer.objects.create(
            session=session,
            direction=RemoteTransfer.Direction.UPLOAD,
            source_path=original_name,
            target_path=request.data.get("target_path") or "",
            original_name=original_name,
            stored_name=stored_name,
            content_type=content_type,
            size_bytes=size_bytes,
            chunk_size=chunk_size,
            total_chunks=math.ceil(size_bytes / chunk_size),
            status=RemoteTransfer.Status.RUNNING,
            created_by=request.user,
        )
        self._transfer_root("tmp", transfer.upload_id.hex)
        log_action(RemoteActivityLog.Action.FILE_UPLOAD, "Started chunked upload.", request.user, session.device, session, {"transfer_id": transfer.id, "name": original_name})
        broadcast_transfer(session, transfer)
        return Response(RemoteTransferSerializer(transfer).data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=True, methods=["get"], url_path="upload-status")
    def upload_status(self, request, pk=None):
        transfer = self._assert_transfer_access(self.get_object())
        return Response(RemoteTransferSerializer(transfer).data)

    @decorators.action(detail=True, methods=["post"], url_path="upload-chunk")
    def upload_chunk(self, request, pk=None):
        transfer = self._assert_transfer_access(self.get_object())
        if transfer.direction != RemoteTransfer.Direction.UPLOAD:
            raise ValidationError("Only upload transfers accept chunks.")
        if transfer.status not in {RemoteTransfer.Status.QUEUED, RemoteTransfer.Status.RUNNING, RemoteTransfer.Status.FAILED}:
            return Response(RemoteTransferSerializer(transfer).data)
        chunk_index = int(request.data.get("chunk_index") if request.data.get("chunk_index") is not None else -1)
        if chunk_index < 0 or chunk_index >= transfer.total_chunks:
            raise ValidationError({"chunk_index": "Chunk index is out of range."})
        uploaded = request.FILES.get("chunk")
        if not uploaded:
            raise ValidationError({"chunk": "Chunk file is required."})
        tmp_dir = self._transfer_root("tmp", transfer.upload_id.hex)
        chunk_path = os.path.join(tmp_dir, f"{chunk_index:08d}.part")
        with open(chunk_path, "wb") as destination:
            for piece in uploaded.chunks():
                destination.write(piece)
        completed = transfer.completed_chunk_numbers
        completed.add(chunk_index)
        completed_chunks = sorted(completed)
        transfer.completed_chunks = completed_chunks
        transfer.transferred_bytes = min(transfer.size_bytes, sum(os.path.getsize(os.path.join(tmp_dir, f"{index:08d}.part")) for index in completed_chunks))
        transfer.status = RemoteTransfer.Status.RUNNING
        transfer.error = ""
        transfer.save(update_fields=["completed_chunks", "transferred_bytes", "status", "error", "updated_at"])
        if len(completed_chunks) == transfer.total_chunks:
            final_dir = self._transfer_root("files", str(transfer.created_by_id or "system"))
            final_path = os.path.join(final_dir, transfer.stored_name)
            with open(final_path, "wb") as destination:
                for index in range(transfer.total_chunks):
                    part_path = os.path.join(tmp_dir, f"{index:08d}.part")
                    if not os.path.exists(part_path):
                        transfer.status = RemoteTransfer.Status.FAILED
                        transfer.error = f"Missing chunk {index} during assembly."
                        transfer.save(update_fields=["status", "error", "updated_at"])
                        raise ValidationError(transfer.error)
                    with open(part_path, "rb") as source:
                        shutil.copyfileobj(source, destination, length=1024 * 1024)
            shutil.rmtree(tmp_dir, ignore_errors=True)
            transfer.storage_path = final_path
            transfer.transferred_bytes = os.path.getsize(final_path)
            transfer.status = RemoteTransfer.Status.COMPLETED
            transfer.save(update_fields=["storage_path", "transferred_bytes", "status", "updated_at"])
            log_action(RemoteActivityLog.Action.FILE_UPLOAD, "Completed chunked upload.", request.user, transfer.session.device, transfer.session, {"transfer_id": transfer.id, "name": transfer.original_name})
        broadcast_transfer(transfer.session, transfer)
        return Response(RemoteTransferSerializer(transfer).data)

    @decorators.action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        transfer = self._assert_transfer_access(self.get_object())
        if transfer.status != RemoteTransfer.Status.COMPLETED or not transfer.storage_path:
            raise Http404("Transfer file is not available.")
        path = os.path.abspath(transfer.storage_path)
        if not os.path.exists(path):
            raise Http404("Transfer file is missing.")
        file_size = os.path.getsize(path)
        content_type = transfer.content_type or mimetypes.guess_type(path)[0] or "application/octet-stream"
        range_header = request.headers.get("Range", "").strip()
        if range_header.startswith("bytes="):
            start_raw, _, end_raw = range_header.removeprefix("bytes=").partition("-")
            start = int(start_raw or 0)
            end = int(end_raw) if end_raw else file_size - 1
            start = max(0, min(start, file_size - 1))
            end = max(start, min(end, file_size - 1))

            def iterator():
                with open(path, "rb") as handle:
                    handle.seek(start)
                    remaining = end - start + 1
                    while remaining > 0:
                        data = handle.read(min(1024 * 1024, remaining))
                        if not data:
                            break
                        remaining -= len(data)
                        yield data

            response = StreamingHttpResponse(iterator(), status=206, content_type=content_type)
            response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
            response["Content-Length"] = str(end - start + 1)
        else:
            response = FileResponse(open(path, "rb"), content_type=content_type)
            response["Content-Length"] = str(file_size)
        response["Accept-Ranges"] = "bytes"
        response["Content-Disposition"] = f'attachment; filename="{transfer.original_name or transfer.stored_name}"'
        return response


class RemoteActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RemoteActivityLogSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["action", "device", "session"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = RemoteActivityLog.objects.select_related("device", "session", "actor")
        if is_admin_level(self.request.user):
            return qs
        return qs.filter(actor=self.request.user)

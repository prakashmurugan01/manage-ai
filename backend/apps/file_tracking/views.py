import csv
from io import StringIO

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.views import APIView

from apps.core.views import api_response
from apps.file_tracking.models import DiskVolume, FileAlert, FileEvent, FileTransfer, TrackingRule
from apps.file_tracking.serializers import (
    DiskVolumeSerializer,
    FileAlertSerializer,
    FileEventSerializer,
    FileTransferCreateSerializer,
    FileTransferSerializer,
    TrackingRuleSerializer,
)
from apps.file_tracking.services import dashboard_summary, record_transfer
from apps.modules.api import BaseModuleViewSet


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


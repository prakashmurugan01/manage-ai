from rest_framework import serializers

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


class DiskVolumeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiskVolume
        fields = "__all__"


class FileTransferSerializer(serializers.ModelSerializer):
    source_volume_label = serializers.CharField(source="source_volume.label", read_only=True)
    destination_volume_label = serializers.CharField(source="destination_volume.label", read_only=True)

    class Meta:
        model = FileTransfer
        fields = "__all__"


class FileTransferCreateSerializer(serializers.Serializer):
    file_name = serializers.CharField(required=False, allow_blank=True)
    source_path = serializers.CharField()
    destination_path = serializers.CharField()
    source_label = serializers.CharField(required=False, allow_blank=True)
    destination_label = serializers.CharField(required=False, allow_blank=True)
    source_disk_type = serializers.ChoiceField(choices=DiskVolume.DiskType.choices, required=False)
    destination_disk_type = serializers.ChoiceField(choices=DiskVolume.DiskType.choices, required=False)
    size_bytes = serializers.IntegerField(min_value=0, default=0)
    checksum = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=FileTransfer.Status.choices, required=False)
    process_name = serializers.CharField(required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False)


class FileEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileEvent
        fields = "__all__"


class FileAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileAlert
        fields = "__all__"
        read_only_fields = ["acknowledged_by", "acknowledged_at", "resolved_at"]


class TrackingRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrackingRule
        fields = "__all__"


class DesktopDeviceSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.get_full_name", read_only=True)

    class Meta:
        model = DesktopDevice
        fields = "__all__"
        read_only_fields = ["owner", "last_seen_at"]


class DeviceConnectionSerializer(serializers.ModelSerializer):
    source_device_name = serializers.CharField(source="source_device.name", read_only=True)
    destination_device_name = serializers.CharField(source="destination_device.name", read_only=True)
    connected_by_name = serializers.CharField(source="connected_by.get_full_name", read_only=True)

    class Meta:
        model = DeviceConnection
        fields = "__all__"
        read_only_fields = ["connected_by", "connected_at", "disconnected_at", "last_error"]


class ProjectFileSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source="uploaded_by.get_full_name", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.get_full_name", read_only=True)
    source_device_name = serializers.CharField(source="source_device.name", read_only=True)
    destination_device_name = serializers.CharField(source="destination_device.name", read_only=True)

    class Meta:
        model = ProjectFile
        fields = "__all__"
        read_only_fields = [
            "stored_name",
            "storage_path",
            "extension",
            "checksum",
            "uploaded_by",
            "approved_by",
            "approved_at",
            "rejected_by",
            "rejected_at",
            "deployed_at",
            "deployed_path",
            "security_scan_status",
            "risk_score",
        ]


class ChunkUploadSessionSerializer(serializers.ModelSerializer):
    project_file_data = ProjectFileSerializer(source="project_file", read_only=True)

    class Meta:
        model = ChunkUploadSession
        fields = "__all__"
        read_only_fields = ["uploaded_by", "received_chunks", "temp_dir", "status", "project_file"]


class DesktopTransferJobSerializer(serializers.ModelSerializer):
    source_device_name = serializers.CharField(source="source_device.name", read_only=True)
    destination_device_name = serializers.CharField(source="destination_device.name", read_only=True)
    uploaded_by_name = serializers.CharField(source="uploaded_by.get_full_name", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.get_full_name", read_only=True)

    class Meta:
        model = DesktopTransferJob
        fields = "__all__"
        read_only_fields = [
            "bytes_transferred",
            "progress_percent",
            "speed_bytes_per_sec",
            "status",
            "started_at",
            "completed_at",
            "last_error",
        ]


class PhysicalStorageFileSerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source="device.name", read_only=True)
    owner_name = serializers.CharField(source="owner.get_full_name", read_only=True)

    class Meta:
        model = PhysicalStorageFile
        fields = "__all__"
        read_only_fields = ["checksum", "uploaded_at"]


class DesktopTransferAuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.get_full_name", read_only=True)

    class Meta:
        model = DesktopTransferAuditLog
        fields = "__all__"

from rest_framework import serializers

from apps.file_tracking.models import DiskVolume, FileAlert, FileEvent, FileTransfer, TrackingRule


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


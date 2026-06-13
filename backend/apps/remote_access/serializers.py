from rest_framework import serializers

from .models import RemoteActivityLog, RemoteDevice, RemoteSession, RemoteTransfer


class RemoteDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = RemoteDevice
        fields = [
            "id",
            "name",
            "hostname",
            "platform",
            "agent_version",
            "token",
            "fingerprint",
            "status",
            "capabilities",
            "metadata",
            "last_seen_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["token", "status", "last_seen_at", "created_at", "updated_at"]


class RemoteSessionSerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source="device.name", read_only=True)
    requested_by_name = serializers.CharField(source="requested_by.email", read_only=True)

    class Meta:
        model = RemoteSession
        fields = [
            "id",
            "device",
            "device_name",
            "requested_by",
            "requested_by_name",
            "token",
            "status",
            "permission",
            "offer",
            "answer",
            "approved_at",
            "started_at",
            "ended_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["requested_by", "token", "status", "answer", "approved_at", "started_at", "ended_at"]


class RemoteTransferSerializer(serializers.ModelSerializer):
    progress_percent = serializers.SerializerMethodField()
    missing_chunks = serializers.SerializerMethodField()

    class Meta:
        model = RemoteTransfer
        fields = "__all__"
        read_only_fields = [
            "upload_id",
            "transferred_bytes",
            "status",
            "error",
            "created_by",
            "created_at",
            "updated_at",
            "completed_chunks",
            "storage_path",
            "stored_name",
            "progress_percent",
            "missing_chunks",
        ]

    def get_progress_percent(self, obj):
        if not obj.size_bytes:
            return 0
        return min(100, round((obj.transferred_bytes / obj.size_bytes) * 100, 2))

    def get_missing_chunks(self, obj):
        if not obj.total_chunks:
            return []
        completed = obj.completed_chunk_numbers
        return [index for index in range(obj.total_chunks) if index not in completed]


class RemoteActivityLogSerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source="device.name", read_only=True)
    session_token = serializers.CharField(source="session.token", read_only=True)
    actor_name = serializers.CharField(source="actor.email", read_only=True)

    class Meta:
        model = RemoteActivityLog
        fields = ["id", "device", "device_name", "session", "session_token", "actor", "actor_name", "action", "message", "metadata", "created_at"]

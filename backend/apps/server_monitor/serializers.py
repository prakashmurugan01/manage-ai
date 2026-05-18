from rest_framework import serializers
from django.core.cache import cache

from .models import DiskMount, Server, ServerMetrics


class ServerMetricsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServerMetrics
        fields = "__all__"


class DiskMountSerializer(serializers.ModelSerializer):
    alert_status = serializers.SerializerMethodField()

    class Meta:
        model = DiskMount
        fields = "__all__"

    def get_alert_status(self, obj):
        if obj.usage_percent >= 95:
            return "critical"
        if obj.usage_percent >= obj.alert_threshold:
            return "warning"
        return "ok"


class ServerSerializer(serializers.ModelSerializer):
    latest_metrics = serializers.SerializerMethodField()
    latest_disk_mounts = serializers.SerializerMethodField()

    class Meta:
        model = Server
        fields = "__all__"

    def get_latest_metrics(self, obj):
        try:
            cached = cache.get(f"server:{obj.id}:metrics")
        except Exception:
            cached = None
        if cached:
            return cached
        metric = obj.metrics.first()
        return ServerMetricsSerializer(metric).data if metric else None

    def get_latest_disk_mounts(self, obj):
        mounts = {}
        for mount in obj.disk_mounts.order_by("mount_point", "-recorded_at"):
            mounts.setdefault(mount.mount_point, mount)
        return DiskMountSerializer(mounts.values(), many=True).data

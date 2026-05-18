from rest_framework import serializers

from apps.webhooks.models import DataSyncLog, Event


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = "__all__"


class DataSyncLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataSyncLog
        fields = "__all__"


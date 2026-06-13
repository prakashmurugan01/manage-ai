from rest_framework import serializers

from apps.projects.models import UCEMilestone, UCEProject, UCETask, UCETimeEntry


class UCEProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = UCEProject
        fields = "__all__"


class UCEMilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = UCEMilestone
        fields = "__all__"


class UCETaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = UCETask
        fields = "__all__"


class UCETimeEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = UCETimeEntry
        fields = "__all__"


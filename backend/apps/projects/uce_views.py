from rest_framework import permissions

from apps.modules.api import BaseModuleViewSet
from apps.projects.models import UCEMilestone, UCEProject, UCETask, UCETimeEntry
from apps.projects.uce_serializers import UCEMilestoneSerializer, UCEProjectSerializer, UCETaskSerializer, UCETimeEntrySerializer


class UCEProjectViewSet(BaseModuleViewSet):
    queryset = UCEProject.objects.select_related("client")
    serializer_class = UCEProjectSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["name", "client__name", "status"]
    ordering_fields = ["deadline", "budget", "actual_cost", "progress", "created_at"]


class UCEMilestoneViewSet(BaseModuleViewSet):
    queryset = UCEMilestone.objects.select_related("project")
    serializer_class = UCEMilestoneSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["title", "project__name"]
    ordering_fields = ["due_date", "completed", "created_at"]


class UCETaskViewSet(BaseModuleViewSet):
    queryset = UCETask.objects.select_related("project", "milestone", "assigned_to")
    serializer_class = UCETaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["title", "project__name", "assigned_to__name", "status", "priority"]
    ordering_fields = ["priority", "status", "estimated_hours", "actual_hours", "created_at"]


class UCETimeEntryViewSet(BaseModuleViewSet):
    queryset = UCETimeEntry.objects.select_related("task", "employee")
    serializer_class = UCETimeEntrySerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["task__title", "employee__name"]
    ordering_fields = ["date", "hours", "billable", "created_at"]


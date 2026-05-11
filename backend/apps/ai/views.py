from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import decorators, status, viewsets
from rest_framework.response import Response

from apps.core.mixins import AuditModelViewSetMixin
from apps.core.permissions import IsAdminLevel, Roles, has_role, is_admin_level
from apps.projects.models import Project
from apps.tasks.models import Task
from apps.tasks.serializers import TaskSerializer

from .models import TaskSuggestion
from .serializers import ApproveSuggestionSerializer, GenerateTaskSuggestionsSerializer, TaskSuggestionSerializer
from .services import TaskSuggestionService

User = get_user_model()


class TaskSuggestionViewSet(AuditModelViewSetMixin, viewsets.ModelViewSet):
    serializer_class = TaskSuggestionSerializer
    audit_entity = "TaskSuggestion"

    def get_permissions(self):
        if self.action in {"generate", "approve", "create", "update", "partial_update", "destroy"}:
            return [IsAdminLevel()]
        from rest_framework.permissions import IsAuthenticated

        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = TaskSuggestion.objects.select_related("project", "created_by")
        if has_role(user, Roles.SUPER_ADMIN):
            scoped = qs
        elif has_role(user, Roles.ADMIN):
            scoped = qs.filter(Q(project__admins=user) | Q(project__owner=user) | Q(project__created_by=user)).distinct()
        elif has_role(user, Roles.DEVELOPER):
            scoped = qs.filter(project__developers=user).distinct()
        elif has_role(user, Roles.CLIENT):
            scoped = qs.filter(project__client=user).distinct()
        elif is_admin_level(user):
            scoped = qs
        else:
            scoped = qs.none()

        project_id = self.request.query_params.get("project")
        if project_id:
            scoped = scoped.filter(project_id=project_id)
        return scoped

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @decorators.action(detail=False, methods=["post"])
    def generate(self, request):
        serializer = GenerateTaskSuggestionsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        visible_projects = Project.objects.all()
        if has_role(request.user, Roles.ADMIN):
            visible_projects = visible_projects.filter(Q(admins=request.user) | Q(owner=request.user) | Q(created_by=request.user)).distinct()
        elif has_role(request.user, Roles.DEVELOPER):
            visible_projects = visible_projects.filter(developers=request.user).distinct()
        elif has_role(request.user, Roles.CLIENT):
            visible_projects = visible_projects.none()
        project = visible_projects.get(pk=serializer.validated_data["project"])
        suggestions = TaskSuggestionService().generate(
            project,
            context=serializer.validated_data.get("context", ""),
            limit=serializer.validated_data["limit"],
        )
        created = [
            TaskSuggestion.objects.create(project=project, created_by=request.user, **suggestion)
            for suggestion in suggestions
        ]
        return Response(TaskSuggestionSerializer(created, many=True, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        suggestion = self.get_object()
        serializer = ApproveSuggestionSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        assignee = None
        if serializer.validated_data.get("assignee"):
            assignee = User.objects.get(pk=serializer.validated_data["assignee"])
        task = Task.objects.create(
            project=suggestion.project,
            title=suggestion.title,
            description=suggestion.description,
            priority=suggestion.priority,
            story_points=suggestion.story_points,
            status=serializer.validated_data.get("status", Task.Status.BACKLOG),
            due_date=serializer.validated_data.get("due_date"),
            assignee=assignee,
            reporter=request.user,
            ai_suggested=True,
        )
        suggestion.status = TaskSuggestion.Status.APPROVED
        suggestion.save(update_fields=["status", "updated_at"])
        return Response(TaskSerializer(task, context={"request": request}).data, status=status.HTTP_201_CREATED)

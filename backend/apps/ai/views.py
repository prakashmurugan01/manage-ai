from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import decorators, status, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import AuditModelViewSetMixin
from apps.core.permissions import IsAdminLevel, Roles, has_role, is_admin_level
from apps.projects.models import Project
from apps.tasks.models import Task
from apps.tasks.serializers import TaskSerializer

from .models import AssistantAttachment, AssistantMessage, AssistantSession, TaskSuggestion
from .serializers import (
    ApproveSuggestionSerializer,
    AssistantChatSerializer,
    AssistantMessageSerializer,
    AssistantSessionSerializer,
    GenerateTaskSuggestionsSerializer,
    TaskSuggestionSerializer,
)
from .services import EnterpriseAssistantService, ROLE_CAPABILITIES, TaskSuggestionService

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


class AssistantSessionViewSet(viewsets.ModelViewSet):
    serializer_class = AssistantSessionSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = AssistantSession.objects.filter(owner=user).select_related("project").prefetch_related("messages")
        project_id = self.request.query_params.get("project")
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @decorators.action(detail=True, methods=["get"])
    def messages(self, request, pk=None):
        session = self.get_object()
        messages = session.messages.prefetch_related("attachments").all()
        return Response(AssistantMessageSerializer(messages, many=True, context={"request": request}).data)

    @decorators.action(detail=False, methods=["post"], parser_classes=[JSONParser, MultiPartParser, FormParser])
    def chat(self, request):
        serializer = AssistantChatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        project = self._visible_project(request.user, data.get("project"))
        session = self._session_for_request(request.user, data, project)
        user_message = AssistantMessage.objects.create(
            session=session,
            role=AssistantMessage.Role.USER,
            content=data["message"],
            metadata={
                "voice": data.get("voice", False),
                "speak": data.get("speak", False),
                "model_provider": data.get("model_provider") or "local",
                "model_name": data.get("model_name") or "manageai-enterprise-local",
            },
        )
        service = EnterpriseAssistantService()
        attachment_analysis = []
        for uploaded in request.FILES.getlist("files"):
            analysis = service.analyze_uploaded_file(uploaded)
            AssistantAttachment.objects.create(
                message=user_message,
                file=uploaded,
                original_name=getattr(uploaded, "name", "upload.bin"),
                content_type=getattr(uploaded, "content_type", "") or "",
                size_bytes=getattr(uploaded, "size", 0) or 0,
                analysis=analysis,
            )
            attachment_analysis.append(analysis)
        history = list(session.messages.order_by("-created_at").values("role", "content")[:8])
        result = service.build_reply(
            request.user,
            data["message"],
            mode=data.get("mode") or session.mode,
            project=project,
            attachments=attachment_analysis,
            history=history,
            requested_provider=data.get("model_provider") or "auto",
        )
        assistant_message = AssistantMessage.objects.create(
            session=session,
            role=AssistantMessage.Role.ASSISTANT,
            content=result.answer,
            metadata={
                "intent": result.intent,
                "actions": result.actions,
                "context": result.context,
                "provider_used": result.provider_used,
                "fallback_used": result.fallback_used,
                "model_provider": data.get("model_provider") or "local",
                "model_name": data.get("model_name") or "manageai-enterprise-local",
            },
        )
        session.memory = {
            **(session.memory or {}),
            "last_intent": result.intent,
            "last_actions": result.actions,
            "last_context": result.context,
        }
        if session.title == "AI Command Session" and data["message"]:
            session.title = data["message"][:80]
        session.mode = data.get("mode") or session.mode
        session.model_provider = data.get("model_provider") or session.model_provider
        session.model_name = data.get("model_name") or session.model_name
        session.save(update_fields=["title", "mode", "model_provider", "model_name", "memory", "updated_at"])
        return Response(
            {
                "session": AssistantSessionSerializer(session, context={"request": request}).data,
                "user_message": AssistantMessageSerializer(user_message, context={"request": request}).data,
                "assistant_message": AssistantMessageSerializer(assistant_message, context={"request": request}).data,
                "intent": result.intent,
                "actions": result.actions,
                "provider_used": result.provider_used,
                "fallback_used": result.fallback_used,
            },
            status=status.HTTP_201_CREATED,
        )

    @decorators.action(detail=False, methods=["get"], url_path="role-policy")
    def role_policy(self, request):
        service = EnterpriseAssistantService()
        return Response(
            {
                "role": getattr(request.user, "role", "GUEST_VIEWER"),
                "context": service.system_context(request.user),
                "roles": ROLE_CAPABILITIES,
                "providers": service.provider_status(),
            }
        )

    def _session_for_request(self, user, data, project):
        session_id = data.get("session")
        if session_id:
            return AssistantSession.objects.get(pk=session_id, owner=user)
        return AssistantSession.objects.create(
            owner=user,
            project=project,
            mode=data.get("mode") or AssistantSession.Mode.GENERAL,
            model_provider=data.get("model_provider") or "local",
            model_name=data.get("model_name") or "manageai-enterprise-local",
        )

    def _visible_project(self, user, project_id):
        if not project_id:
            return None
        qs = Project.objects.all()
        if has_role(user, Roles.SUPER_ADMIN) or is_admin_level(user):
            return qs.get(pk=project_id)
        if has_role(user, Roles.DEVELOPER):
            return qs.filter(Q(developers=user) | Q(teams__members=user)).distinct().get(pk=project_id)
        if has_role(user, Roles.CLIENT):
            return qs.get(pk=project_id, client=user)
        return None

from django.db.models import Q
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from rest_framework import decorators, filters, status, viewsets
from rest_framework.response import Response

from apps.core.mixins import AuditModelViewSetMixin
from apps.core.permissions import Roles, TaskRBACPermission, has_role, is_admin_level
from apps.notifications.services import notify_user

from .models import Task, TaskComment
from .serializers import KanbanMoveSerializer, TaskCommentSerializer, TaskSerializer


class TaskViewSet(AuditModelViewSetMixin, viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [TaskRBACPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "description", "project__name"]
    ordering_fields = ["updated_at", "created_at", "due_date", "priority", "position"]
    ordering = ["position", "-updated_at"]
    audit_entity = "Task"

    def get_queryset(self):
        user = self.request.user
        qs = Task.objects.select_related("project", "assignee", "reporter", "project__client")
        project_id = self.request.query_params.get("project")
        status_value = self.request.query_params.get("status")
        assignee = self.request.query_params.get("assignee")
        priority = self.request.query_params.get("priority")
        if project_id:
            qs = qs.filter(project_id=project_id)
        if status_value:
            qs = qs.filter(status=status_value)
        if assignee:
            qs = qs.filter(assignee_id=assignee)
        if priority:
            qs = qs.filter(priority=priority)
        if getattr(user, "company_id", None):
            qs = qs.filter(Q(project__company_id=user.company_id) | Q(project__company__isnull=True))

        if has_role(user, Roles.SUPER_ADMIN):
            return qs
        if has_role(user, Roles.ADMIN):
            return qs.filter(Q(project__owner=user) | Q(project__admins=user) | Q(project__created_by=user)).distinct()
        if has_role(user, Roles.DEVELOPER):
            return qs.filter(Q(assignee=user) | Q(project__developers=user) | Q(project__teams__members=user)).distinct()
        if has_role(user, Roles.CLIENT):
            return qs.filter(project__client=user).distinct()
        if is_admin_level(user):
            return qs
        return qs.none()

    def perform_create(self, serializer):
        instance = serializer.save(reporter=self.request.user)
        if instance.assignee_id:
            notify_user(
                recipient=instance.assignee,
                sender=self.request.user,
                title="New task assigned",
                message=f"{instance.title} was assigned in {instance.project.name}.",
                task=instance,
                project=instance.project,
            )
        from apps.audit.services import audit_event

        audit_event(self.request, "CREATE", "Task", instance.pk, {"repr": str(instance)})

    def perform_update(self, serializer):
        previous = Task.objects.get(pk=serializer.instance.pk)
        instance = serializer.save()
        progress_changed = previous.progress_percent != instance.progress_percent
        if progress_changed:
            self._notify_project_admins(
                instance,
                title=f"Project {instance.project.progress}% completed",
                message=f"{instance.assignee.get_full_name() or instance.assignee.email if instance.assignee else 'Developer'} updated {instance.title} to {instance.progress_percent}%.",
                type="TASK",
            )
            self._broadcast_task_progress(instance)
        if instance.status == Task.Status.DONE and instance.approval_status != Task.ApprovalStatus.APPROVED:
            instance.approval_status = Task.ApprovalStatus.PENDING
            instance.save(update_fields=["approval_status", "updated_at"])
            self._notify_project_admins(
                instance,
                title="Task ready for approval",
                message=f"{instance.title} is complete and waiting for review.",
                type="TASK",
            )
        if instance.status == Task.Status.BLOCKED and (instance.delay_reason or previous.status != Task.Status.BLOCKED):
            self._notify_project_admins(
                instance,
                title="Developer issue raised",
                message=f"{instance.title} is blocked in {instance.project.name}.",
                type="ALERT",
            )
        if instance.assignee_id:
            notify_user(
                recipient=instance.assignee,
                sender=self.request.user,
                title="Task updated",
                message=f"{instance.title} moved to {instance.get_status_display()}.",
                task=instance,
                project=instance.project,
            )
        from apps.audit.services import audit_event

        audit_event(self.request, "UPDATE", "Task", instance.pk, {"status": instance.status})

    def _broadcast_task_progress(self, task):
        channel_layer = get_channel_layer()
        if not channel_layer:
            return
        payload = {
            "id": task.id,
            "title": task.title,
            "progress_percent": task.progress_percent,
            "status": task.status,
            "project": task.project_id,
            "project_name": task.project.name,
            "project_progress": task.project.progress,
            "developer": task.assignee.email if task.assignee else "",
        }
        recipients = {task.project.owner, task.project.created_by, task.assignee, *task.project.admins.all(), *task.project.developers.all()}
        for recipient in recipients:
            if recipient:
                try:
                    async_to_sync(channel_layer.group_send)(
                        f"user_{recipient.id}",
                        {"type": "task.progress", "task": payload},
                    )
                except Exception:
                    pass

    def _notify_project_admins(self, task, title, message, type="INFO"):
        recipients = {task.project.owner, task.project.created_by, *task.project.admins.all()}
        for recipient in recipients:
            if recipient and recipient.id != self.request.user.id:
                notify_user(
                    recipient=recipient,
                    sender=self.request.user,
                    title=title,
                    message=message,
                    type=type,
                    task=task,
                    project=task.project,
                )

    @decorators.action(detail=True, methods=["patch"])
    def move(self, request, pk=None):
        task = self.get_object()
        serializer = KanbanMoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task.status = serializer.validated_data["status"]
        task.position = serializer.validated_data["position"]
        task.save(update_fields=["status", "position", "updated_at"])
        return Response(TaskSerializer(task, context={"request": request}).data)

    @decorators.action(detail=False, methods=["get"])
    def my(self, request):
        tasks = self.get_queryset().filter(assignee=request.user)
        return Response(TaskSerializer(tasks, many=True, context={"request": request}).data)

    @decorators.action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        task = self.get_object()
        if not is_admin_level(request.user):
            return Response({"detail": "Only Admin and Super Admin can approve work."}, status=status.HTTP_403_FORBIDDEN)
        task.approval_status = Task.ApprovalStatus.APPROVED
        task.status = Task.Status.DONE
        task.approved_by = request.user
        task.approved_at = timezone.now()
        task.review_note = request.data.get("review_note", task.review_note)
        task.save(update_fields=["approval_status", "status", "approved_by", "approved_at", "review_note", "updated_at"])
        if task.assignee:
            notify_user(
                recipient=task.assignee,
                sender=request.user,
                title="Work approved",
                message=f"{task.title} was approved for {task.project.name}.",
                type="SUCCESS",
                task=task,
                project=task.project,
            )
        return Response(TaskSerializer(task, context={"request": request}).data)

    @decorators.action(detail=True, methods=["post"])
    def disapprove(self, request, pk=None):
        task = self.get_object()
        if not is_admin_level(request.user):
            return Response({"detail": "Only Admin and Super Admin can disapprove work."}, status=status.HTTP_403_FORBIDDEN)
        task.approval_status = Task.ApprovalStatus.DISAPPROVED
        task.status = Task.Status.IN_PROGRESS
        task.approved_by = request.user
        task.approved_at = timezone.now()
        task.review_note = request.data.get("review_note", task.review_note)
        task.save(update_fields=["approval_status", "status", "approved_by", "approved_at", "review_note", "updated_at"])
        if task.assignee:
            notify_user(
                recipient=task.assignee,
                sender=request.user,
                title="Changes requested",
                message=f"{task.title} needs updates before approval.",
                type="ALERT",
                task=task,
                project=task.project,
            )
        return Response(TaskSerializer(task, context={"request": request}).data)


class TaskCommentViewSet(AuditModelViewSetMixin, viewsets.ModelViewSet):
    serializer_class = TaskCommentSerializer
    permission_classes = [TaskRBACPermission]
    audit_entity = "TaskComment"

    def get_queryset(self):
        task_qs = TaskViewSet()
        task_qs.request = self.request
        visible_tasks = task_qs.get_queryset().values("id")
        qs = TaskComment.objects.select_related("task", "author").filter(task_id__in=visible_tasks)
        task_id = self.request.query_params.get("task")
        if task_id:
            qs = qs.filter(task_id=task_id)
        if has_role(self.request.user, Roles.CLIENT):
            qs = qs.filter(is_internal=False)
        return qs

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

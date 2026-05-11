from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import decorators, filters, status, viewsets
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response

from apps.core.mixins import AuditModelViewSetMixin
from apps.core.permissions import ProjectRBACPermission, Roles, has_role, is_admin_level
from apps.documents.models import Document
from apps.tasks.serializers import TaskSerializer

from .models import Project
from .serializers import BranchDeploySerializer, GitPushSerializer, ProjectApprovalSerializer, ProjectCommitSerializer, ProjectConnectionSerializer, ProjectFlowSerializer, ProjectSerializer
from .services import GitHubAPIError, GitHubClient, build_project_flow, check_local_connection, deploy_project_from_branch, push_project_to_git, sync_project_commits


class ProjectViewSet(AuditModelViewSetMixin, viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [ProjectRBACPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "slug", "description", "tags"]
    ordering_fields = ["updated_at", "created_at", "due_date", "priority", "progress", "health_score"]
    ordering = ["-updated_at"]
    audit_entity = "Project"

    def get_queryset(self):
        user = self.request.user
        qs = (
            Project.objects.select_related("owner", "client", "created_by")
            .prefetch_related("admins", "developers", "teams", "teams__members")
            .annotate(
                task_count=Count("tasks", distinct=True),
                open_task_count=Count("tasks", filter=~Q(tasks__status="DONE"), distinct=True),
                commit_count=Count("commits", distinct=True),
            )
        )

        status_value = self.request.query_params.get("status")
        priority = self.request.query_params.get("priority")
        deployment = self.request.query_params.get("deployment")
        if status_value:
            qs = qs.filter(status=status_value)
        if priority:
            qs = qs.filter(priority=priority)
        if deployment in {"on", "off"}:
            qs = qs.filter(deployment__is_enabled=(deployment == "on"))
        connection = self.request.query_params.get("connection")
        if connection:
            qs = qs.filter(connection_type=connection)
        if getattr(user, "company_id", None):
            qs = qs.filter(Q(company_id=user.company_id) | Q(company__isnull=True))

        if has_role(user, Roles.SUPER_ADMIN):
            return qs
        if has_role(user, Roles.ADMIN):
            return qs.filter(Q(owner=user) | Q(admins=user) | Q(created_by=user)).distinct()
        if has_role(user, Roles.DEVELOPER):
            return qs.filter(Q(developers=user) | Q(teams__members=user)).distinct()
        if has_role(user, Roles.CLIENT):
            return qs.filter(client=user).distinct()
        if is_admin_level(user):
            return qs
        return qs.none()

    def perform_create(self, serializer):
        owner = serializer.validated_data.get("owner") or self.request.user
        instance = serializer.save(created_by=self.request.user, owner=owner, company=serializer.validated_data.get("company") or getattr(self.request.user, "company", None))
        instance.admins.add(self.request.user)
        team_members = set()
        for team in instance.teams.prefetch_related("members"):
            team_members.update(team.members.all())
        if team_members:
            instance.developers.add(*team_members)
        from apps.notifications.services import notify_user

        recipients = {instance.client, *instance.developers.all(), *instance.admins.all()}
        for recipient in recipients:
            if recipient and recipient.id != self.request.user.id:
                notify_user(
                    recipient=recipient,
                    sender=self.request.user,
                    title="Project assigned",
                    message=f"{instance.name} is now visible in your dashboard.",
                    type="TASK",
                    project=instance,
                )
        from apps.audit.services import audit_event

        audit_event(self.request, "CREATE", "Project", instance.pk, {"repr": str(instance)})

    def perform_update(self, serializer):
        instance = serializer.save()
        team_members = set()
        for team in instance.teams.prefetch_related("members"):
            team_members.update(team.members.all())
        if team_members:
            instance.developers.add(*team_members)
        from apps.audit.services import audit_event

        audit_event(self.request, "UPDATE", "Project", instance.pk, {"repr": str(instance)})

    @decorators.action(detail=True, methods=["get"])
    def kanban(self, request, pk=None):
        project = self.get_object()
        tasks = project.tasks.select_related("assignee", "reporter").order_by("status", "position", "-updated_at")
        return Response(TaskSerializer(tasks, many=True, context={"request": request}).data)

    @decorators.action(detail=True, methods=["get"])
    def analytics(self, request, pk=None):
        project = self.get_object()
        tasks = project.tasks.all()
        return Response(
            {
                "project": ProjectSerializer(project, context={"request": request}).data,
                "tasks_by_status": dict(tasks.values_list("status").annotate(total=Count("id"))),
                "tasks_by_priority": dict(tasks.values_list("priority").annotate(total=Count("id"))),
                "blocked": tasks.filter(status="BLOCKED").count(),
                "overdue": tasks.filter(due_date__lt=project.due_date).exclude(status="DONE").count() if project.due_date else 0,
            }
        )

    @decorators.action(detail=True, methods=["get", "post"])
    def connection(self, request, pk=None):
        project = self.get_object()
        if request.method.lower() == "get":
            return Response(ProjectSerializer(project, context={"request": request}).data)

        serializer = ProjectConnectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = serializer.apply(project)
        if project.connection_type == Project.ConnectionType.GITHUB:
            try:
                sync_project_commits(project, branch=project.selected_branch, limit=10)
            except GitHubAPIError as exc:
                # The connection is still saved so teams can complete token/network setup later.
                project.refresh_from_db()
                data = ProjectSerializer(project, context={"request": request}).data
                data["warning"] = str(exc)
                return Response(data, status=status.HTTP_202_ACCEPTED)
        from apps.audit.services import audit_event

        audit_event(request, "PROJECT_CONNECTION", "Project", project.pk, {"connection_type": project.connection_type})
        project.refresh_from_db()
        return Response(ProjectSerializer(project, context={"request": request}).data)

    @decorators.action(detail=True, methods=["get"])
    def branches(self, request, pk=None):
        project = self.get_object()
        if project.connection_type != Project.ConnectionType.GITHUB:
            raise ValidationError("Project is not connected to GitHub.")
        try:
            branches = GitHubClient().branches(project.github_owner, project.github_repo)
        except GitHubAPIError as exc:
            raise APIException(str(exc)) from exc
        return Response({"branches": branches, "selected_branch": project.selected_branch, "default_branch": project.github_default_branch})

    @decorators.action(detail=True, methods=["get"])
    def commits(self, request, pk=None):
        project = self.get_object()
        branch = request.query_params.get("branch") or project.selected_branch or project.github_default_branch
        commits = project.commits.filter(branch=branch) if branch else project.commits.all()
        if request.query_params.get("refresh") in {"1", "true", "yes"} and request.user and is_admin_level(request.user):
            try:
                sync_project_commits(project, branch=branch, limit=25)
                project.refresh_from_db()
                commits = project.commits.filter(branch=branch) if branch else project.commits.all()
            except GitHubAPIError as exc:
                raise APIException(str(exc)) from exc
        return Response(ProjectCommitSerializer(commits[:50], many=True).data)

    @decorators.action(detail=True, methods=["post"], url_path="sync-git")
    def sync_git(self, request, pk=None):
        project = self.get_object()
        branch = request.data.get("branch") or project.selected_branch or project.github_default_branch
        try:
            commits = sync_project_commits(project, branch=branch, limit=25)
        except GitHubAPIError as exc:
            raise APIException(str(exc)) from exc
        from apps.audit.services import audit_event

        audit_event(request, "GIT_SYNC", "Project", project.pk, {"branch": branch, "commits": len(commits)})
        return Response(ProjectCommitSerializer(commits, many=True).data)

    @decorators.action(detail=True, methods=["post"], url_path="deploy-branch")
    def deploy_branch(self, request, pk=None):
        project = self.get_object()
        if project.documents.exclude(review_status=Document.ReviewStatus.APPROVED).exists():
            return Response({"detail": "All project files must be approved before deployment can be triggered."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = BranchDeploySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        deployment = deploy_project_from_branch(
            project=project,
            user=request.user,
            branch=serializer.validated_data.get("branch"),
            environment=serializer.validated_data.get("environment"),
            notes=serializer.validated_data.get("notes", ""),
        )
        from apps.audit.services import audit_event
        from apps.deployments.serializers import DeploymentControlSerializer

        audit_event(request, "BRANCH_DEPLOY", "Project", project.pk, {"branch": deployment.source_branch, "environment": deployment.environment})
        return Response(DeploymentControlSerializer(deployment, context={"request": request}).data)

    @decorators.action(detail=True, methods=["post"], url_path="push-git")
    def push_git(self, request, pk=None):
        project = self.get_object()
        serializer = GitPushSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            commit = push_project_to_git(
                project=project,
                user=request.user,
                branch=serializer.validated_data.get("branch"),
                commit_message=serializer.validated_data.get("commit_message", ""),
            )
        except GitHubAPIError as exc:
            raise APIException(str(exc)) from exc
        from apps.audit.services import audit_event

        audit_event(request, "GIT_PUSH", "Project", project.pk, {"branch": commit.branch, "sha": commit.sha})
        return Response(ProjectCommitSerializer(commit, context={"request": request}).data)

    @decorators.action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        if not is_admin_level(request.user):
            return Response({"detail": "Only Admin and Super Admin can review projects."}, status=status.HTTP_403_FORBIDDEN)
        project = self.get_object()
        serializer = ProjectApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project.approval_status = serializer.validated_data["approval_status"]
        project.approval_note = serializer.validated_data.get("approval_note", "")
        project.approved_by = request.user
        project.approved_at = timezone.now()
        if project.approval_status == Project.ApprovalStatus.APPROVED:
            project.status = Project.Status.COMPLETED if project.progress >= 100 else project.status
        project.save(update_fields=["approval_status", "approval_note", "approved_by", "approved_at", "status", "updated_at"])
        from apps.notifications.services import notify_user

        recipients = {project.owner, project.created_by, project.client, *project.admins.all(), *project.developers.all()}
        for recipient in recipients:
            if recipient and recipient.id != request.user.id:
                notify_user(
                    recipient=recipient,
                    sender=request.user,
                    title="Project review updated",
                    message=f"{project.name} is now {project.get_approval_status_display()}.",
                    type="SUCCESS" if project.approval_status == Project.ApprovalStatus.APPROVED else "ALERT",
                    project=project,
                )
        return Response(ProjectSerializer(project, context={"request": request}).data)

    @decorators.action(detail=True, methods=["get", "post"], url_path="project-flow")
    def project_flow(self, request, pk=None):
        project = self.get_object()
        if request.method.lower() == "get":
            return Response({"project": project.id, "flow": project.project_flow, "flow_generated_at": project.flow_generated_at})

        if not is_admin_level(request.user):
            return Response({"detail": "Only Admin and Super Admin can update project flow."}, status=status.HTTP_403_FORBIDDEN)
        serializer = ProjectFlowSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        flow = serializer.validated_data.get("flow") or build_project_flow(project, serializer.validated_data.get("prompt", ""))
        project.project_flow = flow
        project.flow_generated_at = timezone.now()
        project.save(update_fields=["project_flow", "flow_generated_at", "updated_at"])

        from apps.audit.services import audit_event

        audit_event(request, "PROJECT_FLOW_UPDATED", "Project", project.pk, {"steps": len(flow)})
        return Response(ProjectSerializer(project, context={"request": request}).data)

    @decorators.action(detail=True, methods=["get"], url_path="local-status")
    def local_status(self, request, pk=None):
        project = self.get_object()
        if project.connection_type != Project.ConnectionType.LOCAL:
            raise ValidationError("Project is not connected to a local URL.")
        return Response(check_local_connection(project))

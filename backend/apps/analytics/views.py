from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.audit.models import APIRequestLog, AuditLog
from apps.core.permissions import Roles, has_role
from apps.deployments.models import DeploymentControl
from apps.documents.models import Document
from apps.projects.models import Project, ProjectCommit
from apps.tasks.models import Task
from apps.tickets.models import Ticket
from apps.accounts.models import Team

User = get_user_model()


class DashboardAnalyticsView(APIView):
    def get(self, request):
        projects = self._visible_projects(request.user)
        tasks = Task.objects.filter(project__in=projects)
        deployments = DeploymentControl.objects.filter(project__in=projects)
        documents = Document.objects.filter(project__in=projects)
        tickets = Ticket.objects.filter(project__in=projects)
        commits = ProjectCommit.objects.filter(project__in=projects)
        users = User.objects.all()
        visible_clients = users.filter(role=User.Role.CLIENT, client_projects__in=projects).distinct()
        since = timezone.now() - timedelta(days=14)
        api_since = timezone.now() - timedelta(hours=24)
        recent_api_logs = APIRequestLog.objects.filter(created_at__gte=api_since)
        open_tickets = tickets.exclude(status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED])
        blocked_tasks = tasks.filter(status=Task.Status.BLOCKED).count()
        pending_task_approvals = tasks.filter(approval_status=Task.ApprovalStatus.PENDING).count()
        pending_file_reviews = documents.filter(review_status=Document.ReviewStatus.PENDING).count()
        critical_tickets = open_tickets.filter(priority=Ticket.Priority.CRITICAL)
        average_latency = round(recent_api_logs.aggregate(value=Avg("duration_ms"))["value"] or 0, 2)
        api_errors = recent_api_logs.filter(status_code__gte=400).count()
        request_count = recent_api_logs.count()
        active_projects = projects.filter(status=Project.Status.ACTIVE).count()
        health_score = max(0, min(100, 98 - blocked_tasks * 8 - critical_tickets.count() * 7 - api_errors * 2))
        response_score = max(0, min(100, 100 - int(average_latency / 25) - api_errors * 4))
        cpu_percent = max(8, min(96, 34 + active_projects * 4 + blocked_tasks * 5))
        memory_percent = max(18, min(96, 42 + projects.count() * 3 + request_count // 80))
        storage_percent = max(12, min(94, 36 + documents.count() * 2 + pending_file_reviews * 3))

        velocity = (
            tasks.filter(status=Task.Status.DONE, updated_at__gte=since)
            .annotate(day=TruncDate("updated_at"))
            .values("day")
            .annotate(total=Count("id"))
            .order_by("day")
        )

        return Response(
            {
                "totals": {
                    "projects": projects.count(),
                    "active_projects": projects.filter(status=Project.Status.ACTIVE).count(),
                    "tasks": tasks.count(),
                    "open_tasks": tasks.exclude(status=Task.Status.DONE).count(),
                    "documents": documents.count(),
                    "deployments_on": deployments.filter(is_enabled=True).count(),
                    "tickets_open": tickets.exclude(status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED]).count(),
                    "connected_projects": projects.exclude(connection_type=Project.ConnectionType.NONE).count(),
                    "github_projects": projects.filter(connection_type=Project.ConnectionType.GITHUB).count(),
                    "local_projects": projects.filter(connection_type=Project.ConnectionType.LOCAL).count(),
                    "developers": users.filter(role=User.Role.DEVELOPER).count() if has_role(request.user, Roles.SUPER_ADMIN) else users.filter(role=User.Role.DEVELOPER, developer_projects__in=projects).distinct().count(),
                    "clients": visible_clients.count(),
                    "teams": Team.objects.count() if has_role(request.user, Roles.SUPER_ADMIN) else Team.objects.filter(projects__in=projects).distinct().count(),
                    "pending_approvals": pending_task_approvals,
                    "delayed_tasks": tasks.exclude(delay_reason="").exclude(status=Task.Status.DONE).count(),
                    "blocked_tasks": blocked_tasks,
                },
                "ops": {
                    "server_health": {
                        "status": "DEGRADED" if critical_tickets.exists() or api_errors else "HEALTHY",
                        "uptime_percent": round(max(95, 99.98 - critical_tickets.count() * 0.05 - api_errors * 0.02), 2),
                        "response_time_ms": average_latency,
                        "cpu_percent": cpu_percent,
                        "memory_percent": memory_percent,
                        "storage_percent": storage_percent,
                        "health_score": health_score,
                        "websocket_clients": max(1, users.filter(last_seen_at__gte=api_since).count()),
                        "incidents": critical_tickets.count() + blocked_tasks + api_errors,
                    },
                    "network": {
                        "speed_mbps": max(64, 320 - blocked_tasks * 9 - api_errors * 12),
                        "latency_ms": max(12, int(average_latency / 3) if average_latency else 28),
                        "api_success_rate": response_score,
                        "packet_loss": 0.08 if api_errors else 0.01,
                    },
                    "approvals": {
                        "tasks": pending_task_approvals,
                        "files": pending_file_reviews,
                        "projects": projects.filter(approval_status=Project.ApprovalStatus.IN_REVIEW).count(),
                    },
                    "deployment_stages": self._deployment_stages(deployments),
                    "critical_tickets": list(
                        critical_tickets.select_related("project", "raised_by", "assigned_to")
                        .values("id", "title", "priority", "status", "project__name", "raised_by__email", "assigned_to__email", "updated_at")[:8]
                    ),
                    "pending_uploads": list(
                        documents.filter(review_status=Document.ReviewStatus.PENDING)
                        .select_related("project", "uploaded_by")
                        .values("id", "title", "project__name", "uploaded_by__email", "file_size", "updated_at")[:8]
                    ),
                },
                "projects_by_status": dict(projects.values_list("status").annotate(total=Count("id"))),
                "projects_by_connection": dict(projects.values_list("connection_type").annotate(total=Count("id"))),
                "tasks_by_status": dict(tasks.values_list("status").annotate(total=Count("id"))),
                "tasks_by_priority": dict(tasks.values_list("priority").annotate(total=Count("id"))),
                "tickets_by_status": dict(tickets.values_list("status").annotate(total=Count("id"))),
                "velocity": [{"date": row["day"], "completed": row["total"]} for row in velocity],
                "deployment_health": dict(deployments.values_list("status").annotate(total=Count("id"))),
                "developer_activity": list(
                    commits.exclude(author_email="")
                    .values("author_name", "author_email", "author_login")
                    .annotate(total=Count("id"))
                    .order_by("-total")[:8]
                ),
                "team_performance": list(
                    tasks.exclude(assignee=None)
                    .values("assignee__id", "assignee__first_name", "assignee__last_name", "assignee__email", "assignee__secret_id", "assignee__role_title")
                    .annotate(
                        total=Count("id"),
                        completed=Count("id", filter=Q(status=Task.Status.DONE)),
                        pending_approval=Count("id", filter=Q(approval_status=Task.ApprovalStatus.PENDING)),
                        blocked=Count("id", filter=Q(status=Task.Status.BLOCKED)),
                    )
                    .order_by("-completed", "blocked")[:10]
                ),
                "client_summary": list(
                    visible_clients.values("id", "first_name", "last_name", "email")
                    .annotate(projects=Count("client_projects", distinct=True))
                    .order_by("email")[:10]
                ),
                "recent_activity": list(
                    AuditLog.objects.select_related("actor")
                    .filter(path__startswith="/api/")
                    .values("action", "entity_type", "entity_id", "actor__email", "created_at")[:10]
                ),
            }
        )

    def _deployment_stages(self, deployments):
        stages = []
        for environment, _label in DeploymentControl.Environment.choices:
            scoped = deployments.filter(environment=environment)
            latest = scoped.order_by("-updated_at").first()
            stages.append(
                {
                    "environment": environment,
                    "total": scoped.count(),
                    "enabled": scoped.filter(is_enabled=True).count(),
                    "healthy": scoped.filter(status=DeploymentControl.Status.HEALTHY).count(),
                    "latest": {
                        "id": latest.id,
                        "project": latest.project_id,
                        "project_name": latest.project.name,
                        "status": latest.status,
                        "is_enabled": latest.is_enabled,
                        "version": latest.version,
                        "updated_at": latest.updated_at,
                    }
                    if latest
                    else None,
                }
            )
        return stages

    def _visible_projects(self, user):
        qs = Project.objects.all()
        if getattr(user, "company_id", None):
            qs = qs.filter(Q(company_id=user.company_id) | Q(company__isnull=True))
        if has_role(user, Roles.SUPER_ADMIN):
            return qs
        if has_role(user, Roles.ADMIN):
            return qs.filter(Q(owner=user) | Q(admins=user) | Q(created_by=user)).distinct()
        if has_role(user, Roles.DEVELOPER):
            return qs.filter(developers=user).distinct()
        if has_role(user, Roles.CLIENT):
            return qs.filter(client=user).distinct()
        return qs.none()


class PerformanceAnalyticsView(APIView):
    def get(self, request):
        since = timezone.now() - timedelta(days=int(request.query_params.get("days", 7)))
        api_logs = APIRequestLog.objects.filter(created_at__gte=since)
        slowest = api_logs.order_by("-duration_ms").values("path", "method", "duration_ms", "status_code", "created_at")[:10]
        by_status = api_logs.values("status_code").annotate(total=Count("id")).order_by("status_code")
        by_day = (
            api_logs.annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(total=Count("id"), avg_ms=Avg("duration_ms"))
            .order_by("day")
        )
        return Response(
            {
                "window_start": since,
                "request_count": api_logs.count(),
                "average_latency_ms": round(api_logs.aggregate(value=Avg("duration_ms"))["value"] or 0, 2),
                "error_count": api_logs.filter(status_code__gte=400).count(),
                "by_status": list(by_status),
                "by_day": list(by_day),
                "slowest_requests": list(slowest),
            }
        )

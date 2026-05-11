from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.deployments.models import DeploymentControl
from apps.projects.models import Project
from apps.tasks.models import Task
from apps.tickets.models import Ticket

User = get_user_model()


class Command(BaseCommand):
    help = "Seed a realistic demo workspace."

    def handle(self, *args, **options):
        password = "ManageAI@12345"
        super_admin = self._user("super@manageai.local", "super", "Avery", "Stone", User.Role.SUPER_ADMIN, password, True)
        admin = self._user("admin@manageai.local", "admin", "Mira", "Kapoor", User.Role.ADMIN, password, True)
        developer = self._user("dev@manageai.local", "dev", "Jon", "Reed", User.Role.DEVELOPER, password, False)
        client = self._user("client@manageai.local", "client", "Nina", "Shah", User.Role.CLIENT, password, False)
        developer.role_title = "AI Developer"
        developer.skills = ["Python", "Django", "React", "AI Automation"]
        developer.bio = "Builds AI-enabled project workflows, dashboards, and delivery automation."
        developer.save(update_fields=["role_title", "skills", "bio"])

        project, _ = Project.objects.get_or_create(
            slug="internal-ops-command-center",
            defaults={
                "name": "Internal Ops Command Center",
                "project_idea": "A unified operating system for project delivery, clients, tickets, approvals, and Git release visibility.",
                "description": "Centralized platform for project delivery, deployment control, analytics, and client file sharing.",
                "technologies_used": ["Django", "React", "Channels", "GitHub"],
                "features_to_implement": ["Admin panel", "Developer profiles", "Ticket auto-assignment", "Approval workflow"],
                "status": Project.Status.ACTIVE,
                "priority": Project.Priority.HIGH,
                "owner": admin,
                "client": client,
                "created_by": super_admin,
                "due_date": timezone.localdate() + timedelta(days=45),
                "budget": 125000,
                "workflow_days": 7,
                "tags": ["saas", "ops", "analytics"],
                "connection_type": Project.ConnectionType.GITHUB,
                "connection_status": Project.ConnectionStatus.CONNECTED,
                "repository_url": "https://github.com/manageai/internal-ops-command-center",
                "github_owner": "manageai",
                "github_repo": "internal-ops-command-center",
                "github_default_branch": "main",
                "selected_branch": "main",
                "hosted_url": "https://ops.manageai.local",
            },
        )
        project.connection_type = Project.ConnectionType.GITHUB
        project.connection_status = Project.ConnectionStatus.CONNECTED
        project.repository_url = "https://github.com/manageai/internal-ops-command-center"
        project.github_owner = "manageai"
        project.github_repo = "internal-ops-command-center"
        project.github_default_branch = "main"
        project.selected_branch = "main"
        project.hosted_url = "https://ops.manageai.local"
        project.save(
            update_fields=[
                "connection_type",
                "connection_status",
                "repository_url",
                "github_owner",
                "github_repo",
                "github_default_branch",
                "selected_branch",
                "hosted_url",
                "updated_at",
            ]
        )
        project.admins.add(admin)
        project.developers.add(developer)

        DeploymentControl.objects.get_or_create(
            project=project,
            defaults={"is_enabled": True, "status": DeploymentControl.Status.HEALTHY, "version": "v1.4.0", "toggled_by": admin},
        )

        tasks = [
            ("Harden JWT refresh flow", Task.Status.IN_PROGRESS, Task.Priority.HIGH, 5),
            ("Build project health dashboard", Task.Status.REVIEW, Task.Priority.HIGH, 8),
            ("Add client document permissions", Task.Status.TODO, Task.Priority.MEDIUM, 3),
            ("Create deployment rollback notes", Task.Status.BACKLOG, Task.Priority.CRITICAL, 3),
            ("Wire audit log filters", Task.Status.DONE, Task.Priority.MEDIUM, 2),
        ]
        for index, (title, status, priority, points) in enumerate(tasks):
            Task.objects.get_or_create(
                project=project,
                title=title,
                defaults={
                    "description": f"Demo task for {title.lower()}.",
                    "status": status,
                    "priority": priority,
                    "assignee": developer,
                    "reporter": admin,
                    "story_points": points,
                    "workflow_day": min(index + 1, 3),
                    "day_progress": {"day_1": 100 if index > 0 else 60, "day_2": 80 if index > 1 else 0, "day_3": 40 if index > 2 else 0},
                    "position": index,
                    "due_date": timezone.localdate() + timedelta(days=7 + index),
                },
            )

        Ticket.objects.get_or_create(
            project=project,
            title="Client reported staging login screenshot issue",
            defaults={
                "description": "Login panel overlaps the screenshot upload preview on smaller client devices.",
                "priority": Ticket.Priority.HIGH,
                "status": Ticket.Status.TRIAGED,
                "source": Ticket.Source.CLIENT,
                "raised_by": client,
                "assigned_to": developer,
            },
        )

        self.stdout.write(self.style.SUCCESS("Demo workspace seeded."))

    def _user(self, email, username, first_name, last_name, role, password, staff):
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "role": role,
                "is_staff": staff,
                "is_superuser": role == User.Role.SUPER_ADMIN,
                "is_active": True,
            },
        )
        if created:
            user.set_password(password)
            user.save()
        return user

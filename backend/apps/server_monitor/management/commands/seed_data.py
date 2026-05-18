from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from apps.api_keys.models import ApiKey
from apps.api_keys.utils import generate_api_key
from apps.crm.models import Company
from apps.hosting.models import HostedProject, HostingLifecycle
from apps.projects.models import Project
from apps.server_monitor.models import DiskMount, Server, ServerMetrics


class Command(BaseCommand):
    help = "Seed Universal Connection Engine demo servers, hosting projects, API keys, and metrics."

    def handle(self, *args, **options):
        User = get_user_model()
        user, _ = User.objects.get_or_create(
            username="uce_admin",
            defaults={"email": "admin@uce.local", "is_staff": True, "is_superuser": True},
        )
        if not user.has_usable_password():
            user.set_password("Admin@12345")
            user.save()

        servers = []
        for idx, ip in enumerate(["127.0.0.1", "10.0.0.11", "10.0.0.12"], start=1):
            server, _ = Server.objects.get_or_create(
                name=f"UCE Node {idx}",
                defaults={"ip_address": ip, "status": "active", "description": "Seeded monitoring target"},
            )
            servers.append(server)
            for hour in range(10):
                ServerMetrics.objects.create(
                    server=server,
                    cpu_percent=20 + idx * 8 + hour,
                    memory_percent=35 + idx * 6 + hour,
                    disk_percent=45 + idx * 5 + hour,
                    uptime_seconds=86400 * idx + hour * 3600,
                    network_bytes_sent=1000000 * (hour + 1),
                    network_bytes_recv=1500000 * (hour + 1),
                )
            DiskMount.objects.create(server=server, mount_point="/", total_gb=256, used_gb=80 + idx * 20, free_gb=176 - idx * 20, usage_percent=35 + idx * 10)

        clients = [Company.objects.get_or_create(name=f"Client {idx}", defaults={"industry": "SaaS"})[0] for idx in range(1, 6)]
        hosted = []
        for idx, client in enumerate(clients, start=1):
            project, created = HostedProject.objects.get_or_create(
                domain=f"client{idx}.example.com",
                defaults={
                    "client": client,
                    "name": f"Client {idx} Platform",
                    "hosting_platform": ["vercel", "railway", "aws", "netlify", "digitalocean"][idx - 1],
                    "deploy_url": f"https://client{idx}.example.com",
                    "status": "live",
                    "expiry_date": timezone.localdate() + timedelta(days=idx * 12),
                    "monthly_cost": 2500 + idx * 500,
                },
            )
            hosted.append(project)
            if created:
                HostingLifecycle.objects.create(project=project, event_type="created", new_expiry=project.expiry_date, performed_by=user)

        for idx in range(1, 4):
            project, _ = Project.objects.get_or_create(
                slug=slugify(f"uce-api-project-{idx}"),
                defaults={"name": f"UCE API Project {idx}", "owner": user, "status": "ACTIVE"},
            )
            if not ApiKey.objects.filter(project=project, name=f"Seed Key {idx}").exists():
                plaintext, encrypted, prefix = generate_api_key()
                ApiKey.objects.create(project=project, name=f"Seed Key {idx}", key_encrypted=encrypted, key_prefix=prefix, role="admin")
                self.stdout.write(f"API key for {project.name}: {plaintext}")

        self.stdout.write(self.style.SUCCESS("Seeded Universal Connection Engine demo data."))

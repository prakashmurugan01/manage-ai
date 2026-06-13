from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from .models import MachineAgent, ManagedProject, ProjectLogEntry, ProjectWebhookEvent, RuntimeMetric
from .services import create_agent


@override_settings(
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class ProjectIntelligenceTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="pi-owner",
            email="pi-owner@example.com",
            password="password12345",
        )
        self.other = get_user_model().objects.create_user(
            username="pi-other",
            email="pi-other@example.com",
            password="password12345",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def test_agent_registration_returns_one_time_token(self):
        response = self.client.post(
            reverse("project-agent-register"),
            {
                "name": "Prakash Workstation",
                "machine_id": "prakash-dev-01",
                "environment": MachineAgent.Environment.DEVELOPMENT,
                "hostname": "devbox",
                "os_name": "Windows",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["plaintext_token"].startswith("mai_agent_"))
        self.assertNotIn("token_hash", response.data)
        self.assertEqual(MachineAgent.objects.get().owner, self.owner)

    def test_agent_ingest_creates_project_metrics_logs_and_webhooks(self):
        agent = create_agent(
            self.owner,
            name="Prakash Workstation",
            machine_id="prakash-dev-01",
            environment=MachineAgent.Environment.DEVELOPMENT,
        )
        response = APIClient().post(
            reverse("project-agent-ingest"),
            {
                "heartbeat": {"name": "Prakash Workstation", "machine_id": "prakash-dev-01", "environment": "development"},
                "projects": [
                    {
                        "external_id": "alpha",
                        "name": "Alpha",
                        "framework": "Next.js",
                        "runtime_status": "running",
                        "build_status": "passing",
                    }
                ],
                "metrics": [{"project_id": "alpha", "cpu_percent": 18, "memory_percent": 42, "requests_per_second": 12}],
                "logs": [{"project_id": "alpha", "level": "error", "message": "Webhook timeout"}],
                "webhook_events": [
                    {
                        "project_id": "alpha",
                        "event_type": "stripe.payment_failed",
                        "status": "failed",
                        "response_code": 500,
                        "processing_time_ms": 2800,
                    }
                ],
            },
            HTTP_AUTHORIZATION=f"Agent {agent.plaintext_token}",
            format="json",
        )

        self.assertEqual(response.status_code, 202)
        project = ManagedProject.objects.get(external_id="alpha")
        self.assertEqual(project.framework, "Next.js")
        self.assertEqual(RuntimeMetric.objects.filter(project=project).count(), 1)
        self.assertEqual(ProjectLogEntry.objects.filter(project=project, level="error").count(), 1)
        webhook = ProjectWebhookEvent.objects.get(project=project)
        self.assertEqual(webhook.ai_analysis["severity"], "critical")

    def test_dashboard_is_scoped_to_agent_owner(self):
        own_agent = create_agent(
            self.owner,
            name="Owned Agent",
            machine_id="owned",
            environment=MachineAgent.Environment.DEVELOPMENT,
        )
        other_agent = create_agent(
            self.other,
            name="Other Agent",
            machine_id="other",
            environment=MachineAgent.Environment.DEVELOPMENT,
        )
        ManagedProject.objects.create(agent=own_agent, external_id="own", environment="development", name="Owned Project")
        ManagedProject.objects.create(agent=other_agent, external_id="other", environment="development", name="Other Project")

        response = self.client.get(reverse("project-intelligence-dashboard"))

        self.assertEqual(response.status_code, 200)
        names = {project["name"] for project in response.data["projects"]}
        agent_names = {agent["name"] for agent in response.data["agents"]}
        self.assertEqual(names, {"Owned Project"})
        self.assertEqual(agent_names, {"Owned Agent"})

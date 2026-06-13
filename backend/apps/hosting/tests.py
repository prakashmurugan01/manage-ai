from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import OperationalError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.notifications.models import Notification

from .health import HealthProbeResult
from .models import DeploymentRun, HostedProject, HostingLifecycle, HostingLink, ProjectUpload, VercelProject
from .tasks import check_hosted_project_health
from .providers import toggle_hosted_project_access
from .vercel import VercelApiError, sync_project_domains, sync_vercel_projects, upsert_vercel_project


class DeploymentProviderSelectionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="deploy-admin", email="deploy-admin@example.com", password="password", role=User.Role.ADMIN, is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.upload = ProjectUpload.objects.create(
            owner=self.user,
            original_name="site.zip",
            upload=ContentFile(b"PK\x05\x06" + b"\x00" * 18, name="site.zip"),
            size_bytes=22,
            status=ProjectUpload.Status.ANALYZED,
            project_type="static",
            analysis={"environment_variables": []},
        )

    def test_deployment_run_has_no_vercel_default(self):
        run = DeploymentRun.objects.create(upload=self.upload)
        self.assertEqual(run.primary_provider, "")

    def test_deploy_requires_explicit_primary_provider(self):
        response = self.client.post(f"/api/hosting/uploads/{self.upload.id}/deploy/", {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["fallback_provider"], None)
        self.assertFalse(DeploymentRun.objects.filter(upload=self.upload, primary_provider="vercel").exists())


class HostedProjectAccessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="password",
            role=User.Role.ADMIN,
            is_staff=True,
        )
        self.project = HostedProject.objects.create(
            name="Example App",
            client_name="Example Client",
            domain="example-app.test",
            hosting_platform=HostedProject.Platform.NETLIFY,
            deploy_url="https://example-app.test",
            status=HostedProject.Status.LIVE,
            tag="active",
            link_is_active=True,
            expiry_date=timezone.localdate() + timedelta(days=365),
        )
        self.link = HostingLink.objects.create(
            project=self.project,
            provider=HostingLink.Provider.NETLIFY,
            label="Primary",
            url="https://example-app.test",
            domain="example-app.test",
            status=HostingLink.Status.ON,
            is_active=True,
            is_enabled=True,
        )

    @patch("apps.hosting.providers.toggle_hosting_link")
    def test_disable_updates_project_links_lifecycle_and_notifications(self, toggle_link):
        def fake_toggle(link, enabled, user=None):
            link.is_enabled = enabled
            link.status = HostingLink.Status.ON if enabled else HostingLink.Status.OFF
            link.save(update_fields=["is_enabled", "status", "updated_at"])
            return link

        toggle_link.side_effect = fake_toggle
        toggle_hosted_project_access(self.project, False, user=self.admin, reason="Maintenance window")

        self.project.refresh_from_db()
        self.link.refresh_from_db()

        self.assertFalse(self.project.link_is_active)
        self.assertEqual(self.project.status, HostedProject.Status.DISABLED)
        self.assertEqual(self.project.tag, "disabled")
        self.assertFalse(self.link.is_enabled)
        self.assertEqual(self.link.status, HostingLink.Status.OFF)
        self.assertTrue(
            HostingLifecycle.objects.filter(
                project=self.project,
                event_type=HostingLifecycle.Event.LINK_DISABLED,
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.admin,
                hosted_project=self.project,
                title="Hosting disabled",
            ).exists()
        )

    @patch("apps.hosting.providers.toggle_hosting_link")
    def test_enable_restores_active_status(self, toggle_link):
        def fake_toggle(link, enabled, user=None):
            link.is_enabled = enabled
            link.status = HostingLink.Status.ON if enabled else HostingLink.Status.OFF
            link.save(update_fields=["is_enabled", "status", "updated_at"])
            return link

        toggle_link.side_effect = fake_toggle
        toggle_hosted_project_access(self.project, False, user=self.admin)
        toggle_hosted_project_access(self.project, True, user=self.admin)

        self.project.refresh_from_db()
        self.link.refresh_from_db()

        self.assertTrue(self.project.link_is_active)
        self.assertEqual(self.project.status, HostedProject.Status.LIVE)
        self.assertEqual(self.project.tag, "active")
        self.assertTrue(self.link.is_enabled)
        self.assertEqual(self.link.status, HostingLink.Status.ON)

    @patch("apps.hosting.views.cache.delete_pattern", create=True)
    @patch("apps.hosting.tasks.check_vercel_links.delay")
    @patch("apps.hosting.tasks.check_all_hosted_project_health.delay")
    def test_refresh_status_tolerates_cache_backend_failure(self, health_delay, vercel_delay, delete_pattern):
        health_delay.return_value = SimpleNamespace(id="health-task")
        vercel_delay.return_value = SimpleNamespace(id="vercel-task")
        delete_pattern.side_effect = ConnectionError("Redis refused")
        client = APIClient()
        client.force_authenticate(self.admin)

        response = client.post("/api/hosting/refresh-status/")

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data["health_task"], "health-task")
        self.assertEqual(response.data["vercel_task"], "vercel-task")
        self.assertFalse(response.data["cache"]["ok"])
        self.assertTrue(response.data["warnings"])


class HostingHealthCheckTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            username="health-admin",
            email="health-admin@example.com",
            password="password",
            role=User.Role.ADMIN,
            is_staff=True,
        )
        self.project = HostedProject.objects.create(
            name="Vercel Preview",
            client_name="Vercel",
            domain="index-62b346a6v-prakash-murugans-projects.vercel.app",
            hosting_platform=HostedProject.Platform.VERCEL,
            deploy_url="https://index-62b346a6v-prakash-murugans-projects.vercel.app",
            status=HostedProject.Status.LIVE,
            tag="active",
            link_is_active=True,
            expiry_date=timezone.localdate() + timedelta(days=365),
        )

    @patch("apps.hosting.tasks.probe_url")
    def test_redirect_is_online(self, probe):
        probe.return_value = HealthProbeResult(
            url=self.project.deploy_url,
            final_url=f"{self.project.deploy_url}/login",
            status_code=302,
            response_time_ms=180,
            online=True,
            dns_ok=True,
            ssl_ok=True,
            redirect_chain=[self.project.deploy_url],
        )

        check_hosted_project_health(self.project.id)
        self.project.refresh_from_db()

        self.assertEqual(self.project.server_status, HostedProject.ServerStatus.ONLINE)
        self.assertTrue(self.project.link_is_active)
        self.assertEqual(self.project.downtime_count, 0)

    @patch("apps.hosting.tasks.probe_url")
    def test_alert_waits_for_three_consecutive_failures(self, probe):
        probe.return_value = HealthProbeResult(
            url=self.project.deploy_url,
            status_code=404,
            response_time_ms=210,
            online=False,
            dns_ok=True,
            ssl_ok=True,
            error="HTTP 404",
        )

        check_hosted_project_health(self.project.id)
        check_hosted_project_health(self.project.id)

        self.project.refresh_from_db()
        self.assertEqual(self.project.server_status, HostedProject.ServerStatus.OFFLINE)
        self.assertTrue(self.project.link_is_active)
        self.assertEqual(Notification.objects.filter(hosted_project=self.project, title__icontains="offline").count(), 0)

        check_hosted_project_health(self.project.id)

        self.assertEqual(Notification.objects.filter(hosted_project=self.project, title__icontains="offline").count(), 1)
        self.assertTrue(self.project.incidents.filter(status="open").exists())

    @patch("apps.hosting.tasks.probe_url")
    def test_recovery_closes_open_incident(self, probe):
        probe.return_value = HealthProbeResult(
            url=self.project.deploy_url,
            status_code=500,
            response_time_ms=300,
            online=False,
            dns_ok=True,
            ssl_ok=True,
            error="HTTP 500",
        )
        for _ in range(3):
            check_hosted_project_health(self.project.id)

        probe.return_value = HealthProbeResult(
            url=self.project.deploy_url,
            status_code=204,
            response_time_ms=90,
            online=True,
            dns_ok=True,
            ssl_ok=True,
        )
        check_hosted_project_health(self.project.id)

        self.project.refresh_from_db()
        self.assertEqual(self.project.server_status, HostedProject.ServerStatus.ONLINE)
        self.assertEqual(self.project.downtime_count, 0)
        self.assertFalse(self.project.incidents.filter(status="open").exists())


class VercelProjectSyncTests(TestCase):
    def test_upsert_handles_empty_deployments_and_targets(self):
        project = upsert_vercel_project(
            {
                "id": "prj_empty",
                "name": "Static Website",
                "latestDeployments": [],
                "targets": {},
            }
        )

        self.assertEqual(project.latest_deployment_url, "")
        self.assertTrue(project.production_domain.endswith(".vercel.app"))
        self.assertEqual(project.production_domain, project.hosted_project.domain)

    def test_upsert_handles_null_deployments_and_target_metadata(self):
        project = upsert_vercel_project(
            {
                "id": "prj_null",
                "name": "Null Target",
                "latestDeployments": None,
                "targets": {
                    "production": {
                        "domain": "https://www.example.com/path",
                        "deployment": None,
                    }
                },
            }
        )

        self.assertEqual(project.production_domain, "www.example.com")
        self.assertEqual(project.latest_deployment_url, "")

    @patch("apps.hosting.providers.sync_vercel_links")
    @patch("apps.hosting.providers.ensure_default_providers")
    def test_sync_skips_invalid_projects_and_continues(self, ensure_providers, sync_links):
        client = FakeVercelClient(
            projects=[
                None,
                {},
                {
                    "id": "prj_good",
                    "name": "Good App",
                    "latestDeployments": [
                        {"id": "dep_good", "url": "good-app.vercel.app", "readyState": "READY"}
                    ],
                    "targets": None,
                },
            ],
            domains={"prj_good": [{"name": "good-app.example.com"}]},
            deployments={
                "prj_good": [
                    "bad-row",
                    {"uid": "", "url": "missing-id.vercel.app"},
                    {"uid": "dep_good", "url": None, "readyState": None, "meta": None},
                ]
            },
        )

        synced = sync_vercel_projects(client)

        self.assertEqual(len(synced), 1)
        self.assertTrue(VercelProject.objects.filter(vercel_id="prj_good").exists())
        project = VercelProject.objects.get(vercel_id="prj_good")
        self.assertEqual(project.latest_deployment_url, "https://good-app.vercel.app")
        self.assertEqual(project.deployments.count(), 1)
        ensure_providers.assert_called_once()
        sync_links.assert_called_once()

    @patch("apps.hosting.providers.sync_vercel_links")
    @patch("apps.hosting.providers.ensure_default_providers")
    def test_sync_continues_when_project_domain_sync_fails(self, *_mocks):
        client = FakeVercelClient(
            projects=[
                {"id": "prj_one", "name": "Project One", "latestDeployments": []},
                {"id": "prj_two", "name": "Project Two", "latestDeployments": []},
            ],
            domain_failures={"prj_one"},
        )

        synced = sync_vercel_projects(client)

        self.assertEqual(len(synced), 2)
        self.assertTrue(VercelProject.objects.filter(vercel_id="prj_one").exists())
        self.assertTrue(VercelProject.objects.filter(vercel_id="prj_two").exists())

    @patch("apps.hosting.vercel.time.sleep")
    @patch("apps.hosting.vercel._positive_int_setting", return_value=2)
    @patch("apps.hosting.vercel._positive_float_setting", return_value=0.001)
    @patch("apps.hosting.vercel.VercelProjectLink.objects.update_or_create")
    def test_domain_sync_retries_transient_database_lock(
        self,
        update_or_create,
        _float_setting,
        _int_setting,
        sleep,
    ):
        project = upsert_vercel_project(
            {
                "id": "prj_retry",
                "name": "Retry App",
                "latestDeployments": [],
            }
        )
        update_or_create.side_effect = [
            OperationalError("database is locked"),
            (object(), True),
        ]
        client = FakeVercelClient(domains={"prj_retry": [{"name": "retry.example.com"}]})

        sync_project_domains(project, client)

        self.assertEqual(update_or_create.call_count, 2)
        sleep.assert_called_once()


class FakeVercelClient:
    def __init__(self, projects=None, domains=None, deployments=None, domain_failures=None):
        self.projects = projects or []
        self.domains = domains or {}
        self.deployments = deployments or {}
        self.domain_failures = set(domain_failures or [])

    def list_projects(self):
        return self.projects

    def list_project_domains(self, project_id_or_name):
        if project_id_or_name in self.domain_failures:
            raise VercelApiError("Domain sync failed.", status_code=502)
        return self.domains.get(project_id_or_name, [])

    def list_deployments(self, project_id=None, project_name=None, limit=20):
        return self.deployments.get(project_id or project_name, [])

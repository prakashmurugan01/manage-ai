import base64
import hashlib
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.projects.models import Project

from .models import ApiKey
from .utils import AuthError, RateLimitExceeded, generate_api_key, validate_api_key


FERNET_KEY = base64.urlsafe_b64encode(hashlib.sha256(b"tests").digest()).decode()


@override_settings(
    API_KEY_FERNET_KEY=FERNET_KEY,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class ApiKeyTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.owner = get_user_model().objects.create_user(
            username="owner",
            email="owner@example.com",
            password="password12345",
        )
        self.other = get_user_model().objects.create_user(
            username="other",
            email="other@example.com",
            password="password12345",
        )
        self.project = Project.objects.create(name="Alpha", slug="alpha", owner=self.owner)
        self.other_project = Project.objects.create(name="Beta", slug="beta", owner=self.other)

    def create_key(self, project=None, **overrides):
        plaintext, encrypted, prefix = generate_api_key()
        api_key = ApiKey.objects.create(
            project=project or self.project,
            name="Test key",
            key_encrypted=encrypted,
            key_prefix=prefix,
            **overrides,
        )
        return plaintext, api_key

    def request(self, ip="127.0.0.1"):
        return self.factory.get("/api/projects/", REMOTE_ADDR=ip)

    def test_valid_key_acceptance(self):
        plaintext, api_key = self.create_key()
        accepted = validate_api_key(self.request(), plaintext)
        self.assertEqual(accepted.id, api_key.id)

    def test_invalid_key_rejection(self):
        with self.assertRaises(AuthError):
            validate_api_key(self.request(), "uce_invalid")

    def test_expired_key_rejection(self):
        plaintext, _ = self.create_key(expires_at=timezone.now() - timedelta(minutes=1))
        with self.assertRaises(AuthError):
            validate_api_key(self.request(), plaintext)

    def test_rate_limit_enforcement(self):
        plaintext, _ = self.create_key(rate_limit_per_minute=1)
        validate_api_key(self.request(), plaintext)
        with self.assertRaises(RateLimitExceeded):
            validate_api_key(self.request(), plaintext)

    def test_ip_whitelist_enforcement(self):
        plaintext, _ = self.create_key(ip_whitelist=["10.0.0.5"])
        with self.assertRaises(AuthError):
            validate_api_key(self.request("127.0.0.1"), plaintext)
        accepted = validate_api_key(self.request("10.0.0.5"), plaintext)
        self.assertIsNotNone(accepted)

    def test_cross_project_isolation(self):
        self.create_key(project=self.project)
        self.create_key(project=self.other_project)
        client = APIClient()
        client.force_authenticate(self.owner)
        response = client.get(reverse("uce-api-keys-list"))
        self.assertEqual(response.status_code, 200)
        returned_projects = {item["project"] for item in response.data["results"]} if "results" in response.data else {item["project"] for item in response.data}
        self.assertEqual(returned_projects, {self.project.id})

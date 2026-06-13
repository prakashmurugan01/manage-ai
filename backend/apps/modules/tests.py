from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User


class ConnectorDefinitionPermissionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.developer = user_model.objects.create_user(
            username="dev",
            email="dev@example.com",
            password="password12345",
            role=User.Role.DEVELOPER,
        )
        self.admin = user_model.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="password12345",
            role=User.Role.ADMIN,
        )
        self.payload = {
            "module_id": "custom-crm",
            "display_name": "Custom CRM",
            "connection_type": "rest_api",
            "base_url": "https://example.com",
            "auth_type": "none",
            "field_mappings": {"name": "full_name"},
            "sync_frequency": 300,
        }

    def test_developer_cannot_create_connector_definition(self):
        client = APIClient()
        client.force_authenticate(self.developer)

        response = client.post(reverse("uce-connectors-list"), self.payload, format="json")

        self.assertEqual(response.status_code, 403)

    def test_admin_can_create_connector_definition(self):
        client = APIClient()
        client.force_authenticate(self.admin)

        response = client.post(reverse("uce-connectors-list"), self.payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["data"]["module_id"], "custom-crm")

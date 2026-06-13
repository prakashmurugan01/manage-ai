from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import RemoteDevice


class RemoteAccessTokenConnectTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="remote-user",
            email="remote-user@example.com",
            password="password",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_connect_token_reports_offline_agent_as_conflict(self):
        device = RemoteDevice.objects.create(name="Acer", owner=self.user, status=RemoteDevice.Status.OFFLINE)

        response = self.client.post(
            "/api/remote-devices/connect-token/",
            {"token": device.token, "permission": "VIEW"},
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "agent_offline")
        self.assertIn("Start the desktop agent", response.data["message"])
        self.assertEqual(response.data["device"]["id"], device.id)

    def test_connect_token_accepts_online_agent(self):
        device = RemoteDevice.objects.create(name="Acer", owner=self.user, status=RemoteDevice.Status.ONLINE)

        response = self.client.post(
            "/api/remote-devices/connect-token/",
            {"token": device.token, "permission": "VIEW"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["device"], device.id)
        self.assertEqual(response.data["status"], "REQUESTED")

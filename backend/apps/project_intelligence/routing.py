from django.urls import path

from .consumers import ProjectAgentConsumer, ProjectIntelligenceConsumer

websocket_urlpatterns = [
    path("ws/project-intelligence/", ProjectIntelligenceConsumer.as_asgi()),
    path("ws/project-agent/", ProjectAgentConsumer.as_asgi()),
]

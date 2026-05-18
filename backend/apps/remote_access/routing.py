from django.urls import path

from .consumers import RemoteAgentConsumer, RemoteDashboardConsumer


websocket_urlpatterns = [
    path("ws/remote-access/", RemoteDashboardConsumer.as_asgi()),
    path("ws/remote-agent/<str:token>/", RemoteAgentConsumer.as_asgi()),
]

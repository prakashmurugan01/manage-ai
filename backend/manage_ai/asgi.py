import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "manage_ai.settings")

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

from apps.realtime.auth import JwtAuthMiddlewareStack
from apps.realtime.routing import websocket_urlpatterns
from apps.remote_access.routing import websocket_urlpatterns as remote_access_websocket_urlpatterns
from apps.webhooks.routing import websocket_urlpatterns as uce_websocket_urlpatterns
from django.urls import path
from apps.server_monitor.consumers import ServerMonitorConsumer
from apps.notifications.consumers import NotificationConsumer
from apps.api_monitor.consumers import ApiMonitorConsumer

django_asgi_app = get_asgi_application()

uce_realtime_patterns = [
    path("ws/server-monitor/", ServerMonitorConsumer.as_asgi()),
    path("ws/notifications/", NotificationConsumer.as_asgi()),
    path("ws/api-monitor/", ApiMonitorConsumer.as_asgi()),
]

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": JwtAuthMiddlewareStack(URLRouter(websocket_urlpatterns + uce_websocket_urlpatterns + remote_access_websocket_urlpatterns + uce_realtime_patterns)),
    }
)

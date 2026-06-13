from django.urls import path

from apps.webhooks.consumers import UCEEventConsumer

websocket_urlpatterns = [
    path("ws/events/", UCEEventConsumer.as_asgi()),
]


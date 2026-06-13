from django.urls import path

from apps.file_tracking.consumers import DesktopTransferConsumer

websocket_urlpatterns = [
    path("ws/file-transfer/", DesktopTransferConsumer.as_asgi()),
]

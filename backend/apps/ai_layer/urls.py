from django.urls import path

from apps.ai_layer.views import AIStatusView

urlpatterns = [
    path("ai/status/", AIStatusView.as_view(), name="uce-ai-status"),
]


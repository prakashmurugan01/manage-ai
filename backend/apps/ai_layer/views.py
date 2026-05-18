from rest_framework import permissions
from rest_framework.views import APIView

from apps.core.views import api_response


class AIStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.conf import settings

        return api_response({"enabled": bool(getattr(settings, "AI_ENABLED", False)), "provider": "anthropic"})


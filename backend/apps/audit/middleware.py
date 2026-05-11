import time

from django.db import OperationalError, ProgrammingError

from .models import APIRequestLog
from .services import get_client_ip


class APIRequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.perf_counter()
        response = self.get_response(request)
        if request.path.startswith("/api/"):
            duration_ms = int((time.perf_counter() - start) * 1000)
            try:
                APIRequestLog.objects.create(
                    user=request.user if getattr(request.user, "is_authenticated", False) else None,
                    path=request.path,
                    method=request.method,
                    status_code=getattr(response, "status_code", 0),
                    duration_ms=duration_ms,
                    ip_address=get_client_ip(request),
                    query_params=dict(request.GET),
                    payload_size=int(request.META.get("CONTENT_LENGTH") or 0),
                    response_size=len(getattr(response, "content", b"")) if hasattr(response, "content") else 0,
                    view_name=getattr(getattr(request, "resolver_match", None), "view_name", "") or "",
                )
            except (OperationalError, ProgrammingError):
                pass
            except Exception:
                pass
        return response

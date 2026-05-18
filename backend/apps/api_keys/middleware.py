import time
import threading

from django.core.cache import cache
from django.http import JsonResponse

from .models import ApiKeyUsageLog
from .utils import AuthError, RateLimitExceeded, validate_api_key


class ApiKeyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.perf_counter()
        if self._should_skip(request.path):
            return self.get_response(request)
        auth = request.headers.get("Authorization", "")
        api_key = None
        if auth.startswith("API_KEY "):
            key = auth.removeprefix("API_KEY ").strip()
            try:
                api_key = validate_api_key(request, key)
            except RateLimitExceeded:
                return JsonResponse({"error": "Rate limit exceeded"}, status=429, headers={"Retry-After": "60"})
            except AuthError:
                return JsonResponse({"error": "Invalid API key"}, status=401)
            request.api_key = api_key
            request.project_scope = api_key.project
        response = self.get_response(request)
        if api_key:
            elapsed = int((time.perf_counter() - start) * 1000)
            log_data = {
                "api_key_id": api_key.id,
                "endpoint": request.path,
                "http_method": request.method,
                "ip_address": self._ip(request),
                "response_code": response.status_code,
                "response_time_ms": elapsed,
            }
            threading.Thread(target=self._log_usage, kwargs=log_data, daemon=True).start()
            now = int(time.time())
            try:
                minute = now // 60
                client = cache.client.get_client(write=True)
                client.zadd(f"api_requests:{minute}", {f"{now}:{api_key.id}:{request.path}": now})
                client.expire(f"api_requests:{minute}", 120)
                cache.set("api_monitor:last_request", {
                    "endpoint": request.path,
                    "method": request.method,
                    "response_code": response.status_code,
                    "response_time_ms": elapsed,
                    "timestamp": now,
                }, 120)
                cache.set(f"api_monitor:request:{now}:{api_key.id}", elapsed, 120)
            except Exception:
                pass
        return response

    def _should_skip(self, path):
        return path.startswith(("/admin/", "/api/auth/", "/ws/"))

    def _ip(self, request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        return (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or "127.0.0.1"

    def _log_usage(self, **kwargs):
        try:
            ApiKeyUsageLog.objects.create(**kwargs)
        except Exception:
            pass

from datetime import timedelta

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.db.models import Avg, Count, Q
from django.utils import timezone

from apps.api_keys.models import ApiKeyUsageLog


@shared_task
def broadcast_api_stats():
    since = timezone.now() - timedelta(seconds=60)
    qs = ApiKeyUsageLog.objects.filter(timestamp__gte=since)
    total = qs.count()
    errors = qs.filter(response_code__gte=400).count()
    top = (
        qs.values("endpoint")
        .annotate(count=Count("id"), avg_response_ms=Avg("response_time_ms"), errors=Count("id", filter=Q(response_code__gte=400)))
        .order_by("-count")[:5]
    )
    payload = {
        "type": "api_stats",
        "requests_last_60s": total,
        "requests_per_sec": round(total / 60, 2),
        "avg_response_time_ms": round(qs.aggregate(value=Avg("response_time_ms"))["value"] or 0, 2),
        "error_rate_percent": round((errors / total) * 100, 2) if total else 0,
        "top_endpoints": [
            {
                "endpoint": row["endpoint"],
                "count": row["count"],
                "avg_response_ms": round(row["avg_response_ms"] or 0, 2),
                "error_rate": round((row["errors"] / row["count"]) * 100, 2) if row["count"] else 0,
            }
            for row in top
        ],
        "recent_logs": list(qs.order_by("-timestamp").values("endpoint", "http_method", "response_code", "response_time_ms", "timestamp")[:50]),
        "timestamp": timezone.now().isoformat(),
    }
    channel_layer = get_channel_layer()
    if channel_layer:
        async_to_sync(channel_layer.group_send)("api_monitor", {"type": "api.stats", "payload": payload})
    return payload


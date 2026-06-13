import time
from datetime import timedelta

from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import TruncHour
from django.utils import timezone
from django.core.cache import cache
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications.services import notify_user
from apps.crm.models import Company, Contact, Deal
from apps.erp.models import Invoice, PurchaseOrder
from apps.inventory.models import InventoryPurchaseOrder, StockLevel
from apps.projects.models import Project
from apps.tickets.models import Ticket
from apps.tickets.serializers import TicketSerializer
from apps.webhooks.models import DataSyncLog, Event

from .models import ApiKey, ApiKeyUsageLog
from .serializers import ApiKeySerializer, ApiKeyUsageLogSerializer
from .utils import generate_api_key


class ApiKeyViewSet(viewsets.ModelViewSet):
    queryset = ApiKey.objects.select_related("project", "project__owner").prefetch_related("usage_logs")
    serializer_class = ApiKeySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["project", "role", "is_active"]
    search_fields = ["name", "key_prefix", "project__name"]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if not user.is_authenticated:
            return qs.none()
        if user.is_superuser:
            return qs
        return qs.filter(project__owner=user)

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        if not self._can_manage(project):
            raise PermissionDenied("Only the project owner can manage API keys.")
        serializer.save()

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        response.data["warning"] = "Store this key securely. It will not be shown again."
        return response

    def perform_update(self, serializer):
        if not self._can_manage(serializer.instance.project):
            raise PermissionDenied("Only the project owner can manage API keys.")
        serializer.save()

    @action(detail=True, methods=["post"])
    def regenerate(self, request, pk=None):
        api_key = self.get_object()
        if not self._can_manage(api_key.project):
            raise PermissionDenied("Only the project owner can manage API keys.")
        plaintext, encrypted, prefix, key_hash = generate_api_key(include_hash=True)
        api_key.key_encrypted = encrypted
        api_key.key_hash = key_hash
        api_key.key_prefix = prefix
        api_key.save(update_fields=["key_encrypted", "key_hash", "key_prefix", "updated_at"])
        data = self.get_serializer(api_key).data
        data["plaintext_key"] = plaintext
        data["warning"] = "Store this key securely. It will not be shown again."
        return Response(data)

    @action(detail=True, methods=["post"])
    def toggle(self, request, pk=None):
        api_key = self.get_object()
        if not self._can_manage(api_key.project):
            raise PermissionDenied("Only the project owner can manage API keys.")
        api_key.is_active = not api_key.is_active
        api_key.save(update_fields=["is_active", "updated_at"])
        return Response(self.get_serializer(api_key).data)

    @action(detail=True, methods=["get"])
    def usage_stats(self, request, pk=None):
        since = timezone.now() - timedelta(hours=24)
        api_key = self.get_object()
        logs = ApiKeyUsageLog.objects.filter(api_key=api_key, timestamp__gte=since)
        hourly = (
            logs
            .annotate(hour=TruncHour("timestamp"))
            .values("hour")
            .annotate(count=Count("id"), avg_response_ms=Avg("response_time_ms"), errors=Count("id", filter=Q(response_code__gte=400)))
            .order_by("hour")
        )
        redis_counts = {}
        try:
            client = cache.client.get_client()
            now_minute = int(timezone.now().timestamp() // 60)
            for minute in range(now_minute - 59, now_minute + 1):
                redis_counts[str(minute)] = client.zcard(f"api_requests:{minute}")
        except Exception:
            redis_counts = {}
        total = logs.count()
        errors = logs.filter(response_code__gte=400).count()
        return Response(
            {
                "hourly": list(hourly),
                "redis_recent_minutes": redis_counts,
                "summary": {
                    "requests_24h": total,
                    "avg_response_time_ms": round(logs.aggregate(value=Avg("response_time_ms"))["value"] or 0, 2),
                    "error_rate_percent": round((errors / total) * 100, 2) if total else 0,
                    "last_used_at": api_key.last_used_at,
                },
            }
        )

    @action(detail=True, methods=["get"])
    def logs(self, request, pk=None):
        logs = self.get_object().usage_logs.all()[:100]
        return Response(ApiKeyUsageLogSerializer(logs, many=True).data)

    @action(detail=True, methods=["get"])
    def usage(self, request, pk=None):
        return self.usage_stats(request, pk)

    @action(detail=True, methods=["get"], url_path="details")
    def details(self, request, pk=None):
        api_key = self.get_object()
        logs = api_key.usage_logs.all()[:100]
        errors = api_key.usage_logs.filter(response_code__gte=400)[:50]
        project = api_key.project
        events = Event.objects.filter(payload__api_key=api_key.key_prefix).order_by("-created_at")[:50]
        tickets = Ticket.objects.filter(project=project, custom_fields__api_key=api_key.key_prefix).select_related("assigned_to")[:50]
        connected_users = []
        if getattr(project, "owner_id", None):
            connected_users.append(
                {
                    "id": project.owner_id,
                    "name": project.owner.get_full_name() or project.owner.get_username(),
                    "role": "owner",
                }
            )
        connected_systems = sorted({event.payload.get("source_platform") for event in events if isinstance(event.payload, dict) and event.payload.get("source_platform")})
        return Response(
            {
                "api_key": self.get_serializer(api_key).data,
                "connected_projects": [{"id": project.id, "name": project.name, "status": getattr(project, "status", ""), "owner_id": getattr(project, "owner_id", None)}],
                "connected_users": connected_users,
                "connected_systems": connected_systems,
                "usage": self.usage_stats(request, pk).data,
                "request_logs": ApiKeyUsageLogSerializer(logs, many=True).data,
                "error_logs": ApiKeyUsageLogSerializer(errors, many=True).data,
                "response_history": ApiKeyUsageLogSerializer(logs, many=True).data,
                "tickets": TicketSerializer(tickets, many=True).data,
                "events": [
                    {
                        "id": event.id,
                        "event_type": event.event_type,
                        "source_platform": event.source_module,
                        "created_at": event.created_at,
                        "payload": event.payload,
                    }
                    for event in events
                ],
            }
        )

    @action(detail=True, methods=["post"], url_path="test")
    def test_request(self, request, pk=None):
        api_key = self.get_object()
        started = time.perf_counter()
        endpoint = request.data.get("endpoint") or "/api/v1/webhooks/events/"
        method = str(request.data.get("method") or "POST").upper()
        simulated_status = int(request.data.get("response_code") or 200)
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        elapsed = int((time.perf_counter() - started) * 1000)
        log = ApiKeyUsageLog.objects.create(
            api_key=api_key,
            endpoint=f"[debug] {method} {endpoint}",
            http_method=method,
            ip_address=request.META.get("REMOTE_ADDR") or "127.0.0.1",
            response_code=simulated_status,
            response_time_ms=elapsed,
        )
        if simulated_status >= 400:
            notify_user(
                recipient=request.user,
                title=f"API debug error for {api_key.name}",
                message=f"{method} {endpoint} returned simulated HTTP {simulated_status}.",
                type="api_abuse",
                urgency="warning",
                project=api_key.project,
            )
        return Response(
            {
                "success": simulated_status < 400,
                "message": "Debug request recorded.",
                "log": ApiKeyUsageLogSerializer(log).data,
                "request": {"method": method, "endpoint": endpoint, "payload": request.data.get("payload", {})},
            },
            status=status.HTTP_200_OK,
        )

    def _can_manage(self, project):
        user = self.request.user
        request_key = getattr(self.request, "api_key", None)
        if request_key and request_key.role == ApiKey.Role.VIEWER:
            return False
        return user.is_superuser or project.owner_id == user.id


class ApiKeyUsageLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ApiKeyUsageLog.objects.select_related("api_key", "api_key__project")
    serializer_class = ApiKeyUsageLogSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["api_key", "http_method", "response_code"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()
        if user.is_superuser:
            return qs
        return qs.filter(api_key__project__owner=user)


class ApiIntelligenceDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        projects = self._visible_projects(request.user)
        project_param = request.query_params.get("project")
        source_param = request.query_params.get("source")
        status_param = request.query_params.get("status")
        window_hours = self._bounded_int(request.query_params.get("window_hours"), default=24, minimum=1, maximum=24 * 30)

        if project_param and project_param != "all":
            projects = projects.filter(id=project_param)

        project_ids = list(projects.values_list("id", flat=True))
        project_id_strings = [str(value) for value in project_ids]
        since = timezone.now() - timedelta(hours=window_hours)

        keys = ApiKey.objects.select_related("project").filter(project__in=projects)
        logs = ApiKeyUsageLog.objects.select_related("api_key", "api_key__project").filter(api_key__project__in=projects)
        window_logs = logs.filter(timestamp__gte=since)

        events = Event.objects.filter(
            Q(entity_type="project", entity_id__in=project_id_strings)
            | Q(payload__project__in=project_ids)
            | Q(payload__project__in=project_id_strings)
            | Q(payload__project_id__in=project_ids)
            | Q(payload__project_id__in=project_id_strings)
        ).order_by("-created_at")
        if source_param and source_param != "all":
            events = events.filter(source_module=source_param)

        api_tickets = Ticket.objects.select_related("project", "assigned_to").filter(project__in=projects).filter(
            Q(source=Ticket.Source.SYSTEM)
            | Q(custom_fields__source_platform__isnull=False)
            | Q(custom_fields__api_key__isnull=False)
            | Q(custom_fields__event_id__isnull=False)
        )
        if status_param and status_param != "all":
            api_tickets = api_tickets.filter(status__iexact=status_param)

        response = {
            "generated_at": timezone.now().isoformat(),
            "window_hours": window_hours,
            "summary": self._summary(keys, window_logs, api_tickets, events),
            "projects": self._project_health(projects, keys, logs, events),
            "api_keys": [self._key_row(key) for key in keys.order_by("project__name", "name")[:250]],
            "complaints": [self._complaint_row(ticket) for ticket in api_tickets.order_by("-created_at")[:120]],
            "complaint_events": [self._event_row(event) for event in events.filter(event_type__icontains="external_issue")[:120]],
            "erp": self._erp_center(),
            "webhooks": self._webhook_center(events, project_id_strings),
            "traffic": self._traffic(window_logs, api_tickets.filter(created_at__gte=since), since, window_hours),
            "security": self._security(keys, logs),
            "anomalies": self._anomalies(keys, window_logs, api_tickets, events),
        }
        return Response(response)

    def _visible_projects(self, user):
        qs = Project.objects.select_related("owner", "client", "company").prefetch_related("admins", "developers")
        if user.is_superuser:
            return qs
        return qs.filter(
            Q(owner=user)
            | Q(client=user)
            | Q(created_by=user)
            | Q(admins=user)
            | Q(developers=user)
        ).distinct()

    def _bounded_int(self, value, default, minimum, maximum):
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return max(minimum, min(maximum, parsed))

    def _summary(self, keys, window_logs, tickets, events):
        request_count = window_logs.count()
        failures = window_logs.filter(response_code__gte=400).count()
        active_keys = keys.filter(is_active=True).count()
        avg_latency = round(window_logs.aggregate(value=Avg("response_time_ms"))["value"] or 0, 2)
        return {
            "active_keys": active_keys,
            "total_keys": keys.count(),
            "requests": request_count,
            "requests_per_minute": round(request_count / 60, 2),
            "avg_latency_ms": avg_latency,
            "failure_rate": round((failures / request_count) * 100, 2) if request_count else 0,
            "failures": failures,
            "open_complaints": tickets.exclude(status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED]).count(),
            "ai_tickets": tickets.count(),
            "webhook_events": events.count(),
        }

    def _project_health(self, projects, keys, logs, events):
        rows = []
        now = timezone.now()
        for project in projects.order_by("name")[:80]:
            project_keys = [key for key in keys if key.project_id == project.id]
            project_logs = logs.filter(api_key__project=project)
            recent_logs = project_logs.filter(timestamp__gte=now - timedelta(hours=24))
            project_events = events.filter(Q(entity_id=str(project.id)) | Q(payload__project=project.id) | Q(payload__project=str(project.id)))
            errors = recent_logs.filter(response_code__gte=400).count()
            total = recent_logs.count()
            environment = "local" if project.connection_type == Project.ConnectionType.LOCAL else "production" if project.hosted_url or project.latest_deployment_url else "workspace"
            rows.append({
                "id": project.id,
                "name": project.name,
                "environment": environment,
                "status": project.system_status or project.status,
                "project_status": project.status,
                "api_status": "degraded" if total and errors / max(total, 1) > 0.05 else "healthy" if project_keys else "not_configured",
                "event_count": project_events.count(),
                "key_count": len(project_keys),
                "request_count_24h": total,
                "failure_count_24h": errors,
                "last_activity": project_events.first().created_at if project_events.exists() else project.updated_at,
                "connection_type": project.connection_type,
                "connection_status": project.connection_status,
                "health_score": project.health_score,
            })
        return rows

    def _key_row(self, key):
        return {
            "id": key.id,
            "project": key.project_id,
            "project_name": key.project.name,
            "name": key.name,
            "key_type": key.key_type,
            "environment": key.environment,
            "key_prefix": key.key_prefix,
            "role": key.role,
            "rate_limit_per_minute": key.rate_limit_per_minute,
            "is_active": key.is_active,
            "ip_whitelist": key.ip_whitelist or [],
            "allowed_scopes": key.allowed_scopes or [],
            "metadata": key.metadata or {},
            "last_used_at": key.last_used_at,
            "expires_at": key.expires_at,
            "created_at": key.created_at,
        }

    def _complaint_row(self, ticket):
        fields = ticket.custom_fields or {}
        customer = fields.get("customer") or {}
        ai = fields.get("ai") or {}
        return {
            "id": ticket.id,
            "ticket_id": ticket.ticket_id,
            "project": ticket.project_id,
            "project_name": ticket.project.name,
            "customer_name": customer.get("name") or fields.get("customer_name") or "Unknown customer",
            "customer_email": customer.get("email") or fields.get("customer_email") or "",
            "customer_phone": customer.get("phone") or fields.get("customer_phone") or "",
            "customer_id": customer.get("id") or fields.get("customer_id") or "",
            "category": ticket.category or fields.get("complaint_category") or ai.get("category") or "General support",
            "priority": ticket.priority,
            "status": ticket.status,
            "summary": ai.get("summary") or ticket.title,
            "sentiment": ai.get("sentiment") or fields.get("sentiment") or "unknown",
            "confidence": ai.get("confidence") or fields.get("ai_confidence") or None,
            "description": ticket.description,
            "conversation": fields.get("conversation_history") or fields.get("conversation") or [],
            "attachments": fields.get("attachments") or [],
            "product": fields.get("product") or {},
            "order": fields.get("order") or {},
            "source_platform": fields.get("source_platform") or "api",
            "external_id": fields.get("external_id") or "",
            "created_at": ticket.created_at,
            "updated_at": ticket.updated_at,
        }

    def _event_row(self, event):
        payload = event.payload or {}
        return {
            "id": event.id,
            "event_type": event.event_type,
            "source_module": event.source_module,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "project": payload.get("project"),
            "project_name": payload.get("project_name"),
            "ticket_id": payload.get("ticket_id"),
            "status": payload.get("status"),
            "payload": payload,
            "processed_at": event.processed_at,
            "created_at": event.created_at,
        }

    def _erp_center(self):
        invoice_qs = Invoice.objects.all()
        purchase_qs = PurchaseOrder.objects.all()
        inventory_po_qs = InventoryPurchaseOrder.objects.all()
        stock_qs = StockLevel.objects.select_related("product")
        low_stock = stock_qs.filter(available_qty__lte=F("product__reorder_level"))
        out_of_stock = stock_qs.filter(available_qty__lte=0)
        customer_qs = Contact.objects.select_related("company").all()
        deal_qs = Deal.objects.select_related("company").all()
        return {
            "summary": {
                "customers": customer_qs.count(),
                "companies": Company.objects.count(),
                "open_deals": deal_qs.exclude(stage__in=["closed_won", "closed_lost"]).count(),
                "revenue": float(invoice_qs.aggregate(value=Sum("total"))["value"] or 0),
                "monthly_sales": float(invoice_qs.filter(created_at__gte=timezone.now() - timedelta(days=30)).aggregate(value=Sum("total"))["value"] or 0),
                "pending_orders": purchase_qs.filter(approval_status__icontains="pending").count() + inventory_po_qs.filter(status__icontains="pending").count(),
                "completed_orders": purchase_qs.filter(approval_status__icontains="approved").count() + inventory_po_qs.filter(status__in=["received", "complete", "completed"]).count(),
                "available_stock": stock_qs.aggregate(value=Sum("available_qty"))["value"] or 0,
                "low_stock_products": low_stock.count(),
                "out_of_stock_products": out_of_stock.count(),
            },
            "customers": [
                {
                    "id": item.id,
                    "name": item.name,
                    "email": item.email,
                    "phone": item.phone,
                    "company": item.company.name if item.company else "",
                    "lifecycle_stage": item.lifecycle_stage,
                    "total_spend": float(item.total_spend or 0),
                    "last_activity": item.last_activity,
                    "updated_at": item.updated_at,
                }
                for item in customer_qs.order_by("-updated_at")[:80]
            ],
            "inventory": [
                {
                    "id": item.id,
                    "sku": item.product.sku,
                    "product": item.product.name,
                    "warehouse": item.warehouse,
                    "available_qty": item.available_qty,
                    "reserved_qty": item.reserved_qty,
                    "reorder_level": item.product.reorder_level,
                    "status": "out_of_stock" if item.available_qty <= 0 else "low_stock" if item.available_qty <= item.product.reorder_level else "healthy",
                    "last_updated": item.last_updated,
                }
                for item in stock_qs.order_by("available_qty")[:100]
            ],
            "sync_logs": [
                {
                    "id": log.id,
                    "source_module": log.source_module,
                    "target_module": log.target_module,
                    "entity_id": log.entity_id,
                    "conflict_detected": log.conflict_detected,
                    "resolution_strategy": log.resolution_strategy,
                    "resolved_at": log.resolved_at,
                    "metadata": log.metadata,
                    "created_at": log.created_at,
                }
                for log in DataSyncLog.objects.order_by("-created_at")[:80]
            ],
        }

    def _webhook_center(self, events, project_id_strings):
        event_rows = list(events[:160])
        return {
            "events": [self._event_row(event) for event in event_rows],
            "local_events": [self._event_row(event) for event in event_rows if str((event.payload or {}).get("environment", "")).lower() == "local"],
            "production_events": [self._event_row(event) for event in event_rows if str((event.payload or {}).get("environment", "")).lower() in {"production", "prod", "live"}],
            "event_types": list(events.values("event_type").annotate(count=Count("id")).order_by("-count")[:20]),
            "project_ids": project_id_strings,
        }

    def _traffic(self, logs, tickets, since, window_hours):
        hourly_logs = (
            logs
            .annotate(hour=TruncHour("timestamp"))
            .values("hour")
            .annotate(requests=Count("id"), errors=Count("id", filter=Q(response_code__gte=400)), avg_latency=Avg("response_time_ms"))
            .order_by("hour")
        )
        hourly_tickets = {
            row["hour"]: row["tickets"]
            for row in tickets.annotate(hour=TruncHour("created_at")).values("hour").annotate(tickets=Count("id"))
        }
        return [
            {
                "time": row["hour"].isoformat() if row["hour"] else "",
                "label": row["hour"].strftime("%m/%d %H:%M") if row["hour"] else "",
                "requests": row["requests"],
                "errors": row["errors"],
                "tickets": hourly_tickets.get(row["hour"], 0),
                "avg_latency": round(row["avg_latency"] or 0, 2),
            }
            for row in hourly_logs
        ] or [{"time": since.isoformat(), "label": f"Last {window_hours}h", "requests": 0, "errors": 0, "tickets": 0, "avg_latency": 0}]

    def _security(self, keys, logs):
        now = timezone.now()
        return {
            "disabled_keys": keys.filter(is_active=False).count(),
            "expired_keys": keys.filter(expires_at__lt=now).count(),
            "unrestricted_keys": keys.filter(Q(ip_whitelist__isnull=True) | Q(ip_whitelist=[])).count(),
            "top_ips": list(logs.exclude(ip_address__isnull=True).values("ip_address").annotate(count=Count("id")).order_by("-count")[:12]),
            "recent_failures": [
                {
                    "id": log.id,
                    "endpoint": log.endpoint,
                    "http_method": log.http_method,
                    "response_code": log.response_code,
                    "response_time_ms": log.response_time_ms,
                    "ip_address": log.ip_address,
                    "key_prefix": log.api_key.key_prefix if log.api_key else "",
                    "project_name": log.api_key.project.name if log.api_key else "",
                    "timestamp": log.timestamp,
                }
                for log in logs.filter(response_code__gte=400).order_by("-timestamp")[:60]
            ],
        }

    def _anomalies(self, keys, logs, tickets, events):
        anomalies = []
        total = logs.count()
        errors = logs.filter(response_code__gte=400).count()
        avg_latency = logs.aggregate(value=Avg("response_time_ms"))["value"] or 0
        if total and errors / total >= 0.05:
            anomalies.append({"severity": "critical", "title": "Elevated API failure rate", "detail": f"{errors} failures in the selected window.", "recommendation": "Inspect failing endpoints, rotate compromised keys if needed, and retry failed webhook deliveries."})
        if avg_latency >= 1000:
            anomalies.append({"severity": "warning", "title": "Latency threshold exceeded", "detail": f"Average API latency is {round(avg_latency, 1)}ms.", "recommendation": "Scale workers and check upstream ERP/CRM dependencies."})
        disabled = keys.filter(is_active=False).count()
        if disabled:
            anomalies.append({"severity": "info", "title": "Disabled integration keys", "detail": f"{disabled} keys are disabled.", "recommendation": "Confirm these integrations have replacement credentials or archive them."})
        urgent = tickets.filter(priority__in=[Ticket.Priority.P1, Ticket.Priority.P2, Ticket.Priority.CRITICAL, Ticket.Priority.HIGH]).exclude(status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED]).count()
        if urgent:
            anomalies.append({"severity": "warning", "title": "High priority external complaints", "detail": f"{urgent} high-priority API-created tickets remain open.", "recommendation": "Route to the project owner and review SLA exposure."})
        conflicts = DataSyncLog.objects.filter(conflict_detected=True, resolved_at__isnull=True).count()
        if conflicts:
            anomalies.append({"severity": "warning", "title": "ERP synchronization conflicts", "detail": f"{conflicts} sync conflicts require resolution.", "recommendation": "Open ERP Management Center and resolve stale entity mappings."})
        if not anomalies:
            anomalies.append({"severity": "healthy", "title": "No active anomaly detected", "detail": "API traffic, ticket automation, ERP sync, and webhook processing are within expected operating bounds.", "recommendation": "Continue monitoring real-time traffic and review access policy regularly."})
        return anomalies


class ExternalIssueIngestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        api_key = getattr(request, "api_key", None)
        project = getattr(request, "project_scope", None)
        if not api_key or not project:
            return Response({"success": False, "error": "Invalid Token", "detail": "Authorization: API_KEY <key> is required."}, status=status.HTTP_401_UNAUTHORIZED)

        payload_type = str(request.data.get("type") or request.data.get("event_type") or "query").lower()
        source_platform = request.data.get("source_platform") or request.data.get("source") or api_key.name
        external_id = request.data.get("external_id") or request.data.get("conversation_id") or request.data.get("message_id")
        incoming_status = request.data.get("status")
        ticket_ref = request.data.get("ticket_id") or request.data.get("ticket")

        if payload_type in {"status_update", "ticket_update", "update"} or ticket_ref:
            ticket = self._find_ticket(project, ticket_ref, external_id)
            if not ticket:
                return Response({"success": False, "error": "Server Down", "detail": "Ticket could not be found for update."}, status=status.HTTP_404_NOT_FOUND)
            ticket_status = self._normalize_ticket_status(incoming_status)
            if ticket_status:
                old_status = ticket.status
                ticket.status = ticket_status
                ticket.custom_fields = {
                    **(ticket.custom_fields or {}),
                    "source_platform": source_platform,
                    "external_id": external_id,
                    "last_external_update": timezone.now().isoformat(),
                    "external_status": incoming_status,
                }
                ticket.save(update_fields=["status", "custom_fields", "updated_at"])
                Event.objects.create(
                    event_type="external_issue.updated",
                    source_module=str(source_platform)[:50],
                    entity_type="ticket",
                    entity_id=str(ticket.id),
                    payload={
                        "title": ticket.title,
                        "project": project.id,
                        "ticket_id": ticket.ticket_id,
                        "source_platform": source_platform,
                        "external_id": external_id,
                        "status": ticket.status,
                        "previous_status": old_status,
                        "raw": request.data,
                    },
                )
            return Response({"success": True, "status": ticket.status.lower(), "data": TicketSerializer(ticket).data})

        title = request.data.get("title") or request.data.get("issue") or request.data.get("query") or "External chatbot query"
        description = request.data.get("description") or request.data.get("details") or request.data.get("message") or request.data.get("complaint") or ""
        priority = Ticket.normalize_priority(str(request.data.get("priority") or "P3").upper())
        intelligence = self._classify_complaint(title, description, request.data)
        customer = self._customer_payload(request.data)
        integration_context = {
            "source_platform": source_platform,
            "external_id": external_id,
            "message_type": payload_type,
            "api_key": api_key.key_prefix,
            "api_key_type": api_key.key_type,
            "environment": api_key.environment,
            "customer": customer,
            "customer_name": customer.get("name", ""),
            "customer_email": customer.get("email", ""),
            "customer_phone": customer.get("phone", ""),
            "customer_id": customer.get("id", ""),
            "conversation_history": request.data.get("conversation_history") or request.data.get("conversation") or request.data.get("messages") or [],
            "attachments": request.data.get("attachments") or request.data.get("images") or request.data.get("files") or [],
            "product": request.data.get("product") or request.data.get("product_details") or {},
            "order": request.data.get("order") or request.data.get("order_information") or {},
            "complaint_category": request.data.get("category") or request.data.get("complaint_category") or intelligence["category"],
            "sentiment": request.data.get("sentiment") or intelligence["sentiment"],
            "ai": intelligence,
        }

        event = Event.objects.create(
            event_type="external_issue.created",
            source_module=str(source_platform)[:50],
            entity_type="project",
            entity_id=str(project.id),
            payload={
                "title": title,
                "description": description,
                "source_platform": source_platform,
                "api_key_type": api_key.key_type,
                "environment": api_key.environment,
                "project": project.id,
                "external_id": external_id,
                "message_type": payload_type,
                "status": "open",
                "customer": customer,
                "ai": intelligence,
                "raw": request.data,
            },
        )
        ticket = Ticket.objects.create(
            project=project,
            title=title[:220],
            description=description or title,
            priority=priority,
            status=Ticket.Status.OPEN,
            source=Ticket.Source.SYSTEM,
            category=integration_context["complaint_category"],
            custom_fields={**integration_context, "event_id": str(event.id)},
        )
        event.payload = {
            **event.payload,
            "ticket_id": ticket.ticket_id,
            "ticket": ticket.id,
            "ticket_status": ticket.status,
            "project_name": project.name,
        }
        event.save(update_fields=["payload"])
        return Response(
            {
                "success": True,
                "status": "open",
                "data": {
                    "ticket_id": ticket.ticket_id,
                    "ticket": ticket.id,
                    "event": event.id,
                    "project": project.id,
                    "source_platform": source_platform,
                },
            },
            status=status.HTTP_201_CREATED,
        )

    def _find_ticket(self, project, ticket_ref, external_id):
        qs = Ticket.objects.filter(project=project)
        if ticket_ref:
            ticket = qs.filter(ticket_id=ticket_ref).first()
            if not ticket:
                try:
                    ticket = qs.filter(id=int(ticket_ref)).first()
                except (TypeError, ValueError):
                    ticket = None
            if ticket:
                return ticket
        if external_id:
            return qs.filter(custom_fields__external_id=external_id).first()
        return None

    def _normalize_ticket_status(self, value):
        normalized = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
        aliases = {
            "OPEN": Ticket.Status.OPEN,
            "NEW": Ticket.Status.OPEN,
            "IN_PROGRESS": Ticket.Status.IN_PROGRESS,
            "PROGRESS": Ticket.Status.IN_PROGRESS,
            "TESTING": Ticket.Status.TESTING,
            "QA": Ticket.Status.TESTING,
            "PENDING": Ticket.Status.PENDING,
            "RESOLVED": Ticket.Status.RESOLVED,
            "CLOSED": Ticket.Status.CLOSED,
        }
        return aliases.get(normalized)

    def _customer_payload(self, data):
        customer = data.get("customer") if isinstance(data.get("customer"), dict) else {}
        return {
            "id": customer.get("id") or data.get("customer_id") or data.get("user_id") or "",
            "name": customer.get("name") or data.get("customer_name") or data.get("name") or "",
            "email": customer.get("email") or data.get("customer_email") or data.get("email") or "",
            "phone": customer.get("phone") or data.get("customer_phone") or data.get("phone") or "",
        }

    def _classify_complaint(self, title, description, data):
        text = " ".join([str(title or ""), str(description or ""), str(data.get("complaint") or ""), str(data.get("message") or "")]).lower()
        category_rules = [
            ("payment", ["payment", "refund", "charge", "billing", "invoice", "failed"]),
            ("delivery", ["delivery", "delivered", "shipping", "courier", "late", "order"]),
            ("product", ["broken", "damaged", "defect", "quality", "product"]),
            ("service", ["support", "agent", "service", "rude", "response"]),
            ("account", ["login", "password", "account", "access", "auth"]),
        ]
        category = data.get("category") or data.get("complaint_category") or "general"
        for candidate, terms in category_rules:
            if any(term in text for term in terms):
                category = candidate
                break
        negative_terms = ["not", "never", "failed", "angry", "bad", "issue", "problem", "refund", "complaint", "broken", "late", "missing", "cancel"]
        urgent_terms = ["urgent", "critical", "escalate", "lawsuit", "fraud", "down", "blocked"]
        sentiment = data.get("sentiment") or ("negative" if any(term in text for term in negative_terms) else "neutral")
        confidence = 94 if sentiment == "negative" else 72
        if any(term in text for term in urgent_terms):
            confidence = min(99, confidence + 4)
        summary = data.get("ai_summary") or data.get("summary") or (description or title or "External customer issue")[:280]
        return {
            "category": category,
            "sentiment": sentiment,
            "confidence": confidence,
            "summary": summary,
            "detector": "rules.v1",
        }

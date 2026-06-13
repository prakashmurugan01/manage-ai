import re
import time
from decimal import Decimal

from django.db.models import F, Q, Sum
from django.utils import timezone

from apps.core.models import UniversalQuery


MODULE_KEYWORDS = {
    "crm": {"customer", "customers", "contact", "company", "deal", "activity", "client"},
    "erp": {"invoice", "invoices", "finance", "financial", "account", "overdue", "budget", "paid"},
    "hr": {"employee", "employees", "payroll", "department", "leave", "staff"},
    "inventory": {"inventory", "stock", "supply", "warehouse", "product", "purchase order", "supplier"},
    "projects": {"project", "projects", "task", "milestone", "deadline", "delayed", "over-budget"},
    "file_tracking": {"file", "files", "disk", "drive", "usb", "network", "transfer", "copy", "move", "movement", "tracking"},
}


class UniversalQueryProcessor:
    def execute(self, raw_input, query_type="nl", modules=None, limit=50, offset=0, user=None):
        started = time.perf_counter()
        query_type = "nl" if query_type == "natural_language" else query_type
        iql = self.normalize(raw_input, query_type, modules, limit, offset)
        query = UniversalQuery.objects.create(
            raw_input=raw_input,
            query_type=query_type,
            normalized_iql=iql,
            target_modules=iql["modules"],
            created_by=user if getattr(user, "is_authenticated", False) else None,
        )
        results = self.route(iql)
        sliced = results[offset : offset + limit]
        execution_ms = int((time.perf_counter() - started) * 1000)
        query.executed_at = timezone.now()
        query.execution_ms = execution_ms
        query.result_count = len(results)
        query.save(update_fields=["executed_at", "execution_ms", "result_count", "updated_at"])
        return {
            "query_id": str(query.query_id),
            "results": sliced,
            "modules_queried": iql["modules"],
            "execution_ms": execution_ms,
            "total_count": len(results),
            "ai_explanation": None,
        }

    def normalize(self, raw_input, query_type, modules=None, limit=50, offset=0):
        text = raw_input.strip()
        detected_modules = modules or self.detect_modules(text)
        return {
            "input": text,
            "query_type": query_type,
            "intent": self.detect_intent(text),
            "modules": detected_modules,
            "filters": self.extract_filters(text),
            "limit": limit,
            "offset": offset,
        }

    def detect_modules(self, text):
        normalized = text.lower()
        modules = [module for module, keywords in MODULE_KEYWORDS.items() if any(keyword in normalized for keyword in keywords)]
        return modules or ["crm", "erp", "hr", "inventory", "projects", "file_tracking"]

    def detect_intent(self, text):
        normalized = text.lower()
        if "delayed" in normalized and ("supply" in normalized or "stock" in normalized):
            return "projects_delayed_supply_chain"
        if "inactive" in normalized and ("high-value" in normalized or "high value" in normalized or "customers" in normalized):
            return "inactive_high_value_customers"
        if "employee" in normalized and ("over-budget" in normalized or "over budget" in normalized):
            return "employees_over_budget_projects"
        if any(keyword in normalized for keyword in ["file", "disk", "drive", "usb", "transfer"]):
            return "file_transfer_search"
        if normalized.startswith("select"):
            return "sql_read"
        return "module_search"

    def extract_filters(self, text):
        filters = {}
        money = re.search(r"(?:\$|usd\s*)?([0-9][0-9,]*(?:\.[0-9]+)?)", text.lower())
        if money:
            filters["amount"] = str(Decimal(money.group(1).replace(",", "")))
        days = re.search(r"last\s+([0-9]+)\s+days", text.lower())
        if days:
            filters["days"] = int(days.group(1))
        return filters

    def route(self, iql):
        intent = iql["intent"]
        if intent == "projects_delayed_supply_chain":
            return self.projects_delayed_supply_chain()
        if intent == "inactive_high_value_customers":
            return self.inactive_high_value_customers(iql["filters"])
        if intent == "employees_over_budget_projects":
            return self.employees_over_budget_projects()
        if intent == "file_transfer_search":
            return self.file_transfer_search(iql)
        return self.module_search(iql)

    def module_search(self, iql):
        text = iql["input"]
        results = []
        if "crm" in iql["modules"]:
            from apps.crm.models import Company, Contact, Deal

            results.extend({"module": "crm", "entity": "company", "id": str(obj.id), "name": obj.name} for obj in Company.objects.filter(is_deleted=False, name__icontains=text)[:25])
            results.extend({"module": "crm", "entity": "contact", "id": str(obj.id), "name": obj.name, "email": obj.email} for obj in Contact.objects.filter(is_deleted=False, name__icontains=text)[:25])
            results.extend({"module": "crm", "entity": "deal", "id": str(obj.id), "title": obj.title, "value": str(obj.value)} for obj in Deal.objects.filter(is_deleted=False, title__icontains=text)[:25])
        if "inventory" in iql["modules"]:
            from apps.inventory.models import Product

            results.extend({"module": "inventory", "entity": "product", "id": str(obj.id), "sku": obj.sku, "name": obj.name} for obj in Product.objects.filter(is_deleted=False, name__icontains=text)[:25])
        if "file_tracking" in iql["modules"]:
            results.extend(self.file_transfer_search(iql))
        return results

    def file_transfer_search(self, iql):
        from apps.file_tracking.models import FileAlert, FileTransfer

        text = iql["input"]
        transfers = FileTransfer.objects.filter(is_deleted=False).filter(
            Q(file_name__icontains=text)
            | Q(source_path__icontains=text)
            | Q(destination_path__icontains=text)
            | Q(file_extension__icontains=text)
            | Q(status__icontains=text)
        )
        if not transfers.exists():
            transfers = FileTransfer.objects.filter(is_deleted=False)
        results = [
            {
                "module": "file_tracking",
                "entity": "transfer",
                "id": str(transfer.id),
                "file_name": transfer.file_name,
                "size_bytes": transfer.size_bytes,
                "source_path": transfer.source_path,
                "destination_path": transfer.destination_path,
                "status": transfer.status,
                "risk_score": transfer.risk_score,
            }
            for transfer in transfers[:50]
        ]
        if "alert" in text.lower() or "unusual" in text.lower() or "suspicious" in text.lower():
            results.extend(
                {
                    "module": "file_tracking",
                    "entity": "alert",
                    "id": str(alert.id),
                    "severity": alert.severity,
                    "status": alert.status,
                    "message": alert.message,
                }
                for alert in FileAlert.objects.filter(is_deleted=False).exclude(status="resolved")[:25]
            )
        return results

    def projects_delayed_supply_chain(self):
        from apps.inventory.models import InventoryPurchaseOrder, StockLevel
        from apps.projects.models import UCEProject

        delayed_projects = UCEProject.objects.filter(is_deleted=False).filter(Q(status__in=["delayed", "at_risk"]) | Q(deadline__lt=timezone.localdate(), progress__lt=100))
        constrained_skus = set(
            StockLevel.objects.filter(is_deleted=False, available_qty__lte=F("product__reorder_level")).values_list("product__sku", flat=True)
        )
        late_orders = list(
            InventoryPurchaseOrder.objects.filter(is_deleted=False)
            .filter(Q(status__in=["ordered", "delayed"]) | Q(expected_delivery__lt=timezone.localdate(), received_at__isnull=True))
            .values("id", "supplier", "items", "status", "expected_delivery")
        )
        results = []
        for project in delayed_projects.select_related("client"):
            related_orders = [order for order in late_orders if self._items_touch_skus(order["items"], constrained_skus)]
            if related_orders:
                results.append(
                    {
                        "module": "projects",
                        "project_id": str(project.id),
                        "project": project.name,
                        "status": project.status,
                        "deadline": project.deadline,
                        "progress": project.progress,
                        "supply_chain_orders": related_orders,
                    }
                )
        return results

    def inactive_high_value_customers(self, filters):
        from apps.crm.models import Company
        from apps.erp.models import Invoice

        days = filters.get("days", 60)
        threshold = Decimal(filters.get("amount", "5000"))
        since = timezone.now() - timezone.timedelta(days=days)
        invoices = (
            Invoice.objects.filter(is_deleted=False, status__in=["sent", "overdue", "paid"])
            .values("company_id")
            .annotate(total_revenue=Sum("total"))
            .filter(total_revenue__gte=threshold)
        )
        company_ids = [row["company_id"] for row in invoices]
        totals = {row["company_id"]: row["total_revenue"] for row in invoices}
        companies = Company.objects.filter(id__in=company_ids, is_deleted=False).filter(Q(contacts__last_activity__lt=since) | Q(contacts__last_activity__isnull=True)).distinct()
        return [
            {
                "module": "crm",
                "company_id": str(company.id),
                "company": company.name,
                "status": company.status,
                "total_revenue": str(totals.get(company.id, 0)),
                "inactive_days": days,
            }
            for company in companies
        ]

    def employees_over_budget_projects(self):
        from apps.projects.models import UCETask, UCETimeEntry

        over_budget_tasks = UCETask.objects.filter(is_deleted=False, project__is_deleted=False, project__actual_cost__gt=F("project__budget")).select_related("project", "assigned_to")
        results = []
        for task in over_budget_tasks:
            hours = UCETimeEntry.objects.filter(is_deleted=False, task=task).aggregate(total=Sum("hours"))["total"] or Decimal("0")
            results.append(
                {
                    "module": "hr",
                    "employee_id": str(task.assigned_to_id) if task.assigned_to_id else None,
                    "employee": task.assigned_to.name if task.assigned_to_id else "Unassigned",
                    "project_id": str(task.project_id),
                    "project": task.project.name,
                    "budget": str(task.project.budget),
                    "actual_cost": str(task.project.actual_cost),
                    "task": task.title,
                    "hours": str(hours),
                }
            )
        return results

    def _items_touch_skus(self, items, skus):
        if not skus:
            return bool(items)
        for item in items or []:
            if item.get("sku") in skus or item.get("product_sku") in skus:
                return True
        return False

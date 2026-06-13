from django.apps import AppConfig


class ErpConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.erp"
    label = "erp"
    module_id = "erp"
    display_name = "ERP"
    version = "1.0.0"
    supported_query_types = ["rest", "nl"]
    schema = {
        "Invoice": {"company": "uuid", "total": "decimal", "status": "string", "due_date": "date"},
        "PurchaseOrder": {"vendor": "string", "items": "json", "total": "decimal"},
        "FinancialAccount": {"name": "string", "type": "string", "balance": "decimal"},
        "JournalEntry": {"amount": "decimal", "reference": "string"},
    }
    endpoints = ["/api/v1/erp/invoices/", "/api/v1/erp/purchase-orders/", "/api/v1/erp/accounts/", "/api/v1/erp/journal-entries/"]

    def ready(self):
        from apps.erp import signals  # noqa: F401


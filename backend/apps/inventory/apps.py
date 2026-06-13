from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.inventory"
    label = "inventory"
    module_id = "inventory"
    display_name = "Inventory"
    version = "1.0.0"
    supported_query_types = ["rest", "nl"]
    schema = {
        "Product": {"sku": "string", "name": "string", "reorder_level": "integer"},
        "StockLevel": {"product": "uuid", "warehouse": "string", "available_qty": "integer"},
        "InventoryPurchaseOrder": {"supplier": "string", "items": "json", "status": "string"},
        "StockMovement": {"product": "uuid", "movement_type": "string", "quantity": "integer"},
    }
    endpoints = ["/api/v1/inventory/products/", "/api/v1/inventory/stock-levels/", "/api/v1/inventory/purchase-orders/", "/api/v1/inventory/stock-movements/"]

    def ready(self):
        from apps.inventory import signals  # noqa: F401


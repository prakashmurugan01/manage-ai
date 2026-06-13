from django.db import models

from apps.core.models import UCEModel


class Product(UCEModel):
    sku = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=180, db_index=True)
    category = models.CharField(max_length=120, blank=True, db_index=True)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reorder_level = models.PositiveIntegerField(default=0, db_index=True)
    lead_time_days = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["sku"]
        indexes = [models.Index(fields=["category", "name"])]

    def __str__(self):
        return f"{self.sku} {self.name}"


class StockLevel(UCEModel):
    product = models.ForeignKey("inventory.Product", related_name="stock_levels", on_delete=models.CASCADE, db_index=True)
    warehouse = models.CharField(max_length=120, db_index=True)
    quantity = models.IntegerField(default=0)
    reserved_qty = models.IntegerField(default=0)
    available_qty = models.IntegerField(default=0, db_index=True)
    last_updated = models.DateTimeField(auto_now=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["warehouse", "product__sku"]
        constraints = [models.UniqueConstraint(fields=["product", "warehouse"], name="unique_product_warehouse_stock")]

    def __str__(self):
        return f"{self.product} {self.warehouse}"


class InventoryPurchaseOrder(UCEModel):
    supplier = models.CharField(max_length=180, db_index=True)
    items = models.JSONField(default=list)
    status = models.CharField(max_length=40, default="draft", db_index=True)
    expected_delivery = models.DateField(null=True, blank=True, db_index=True)
    received_at = models.DateTimeField(null=True, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["expected_delivery", "-created_at"]
        indexes = [models.Index(fields=["status", "expected_delivery"])]

    def __str__(self):
        return f"{self.supplier} {self.status}"


class StockMovement(UCEModel):
    product = models.ForeignKey("inventory.Product", related_name="stock_movements", on_delete=models.CASCADE, db_index=True)
    movement_type = models.CharField(max_length=40, db_index=True)
    quantity = models.IntegerField()
    reference_doc = models.CharField(max_length=140, blank=True, db_index=True)
    warehouse = models.CharField(max_length=120, db_index=True)
    moved_at = models.DateTimeField(db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-moved_at"]

    def __str__(self):
        return f"{self.product} {self.movement_type} {self.quantity}"

